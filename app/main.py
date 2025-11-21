"""Main FastAPI application for genealogy data pipeline"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from app.api.endpoints import ingest, leads, jobs, files, converter
from app.database import init_db, get_db
from app import models  # Import all models to register them with Base
from app.models.processing_job import ProcessingJob
from app.models.person import Person
from app.models.source import Source
from sqlalchemy.orm import Session
from pathlib import Path
import logging
import json
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Genealogy Data Pipeline API",
    description="Backend system for processing genealogy records and identifying German citizenship eligibility leads",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers with /api prefix
app.include_router(ingest.router, prefix="/api", tags=["Ingestion"])
app.include_router(leads.router, prefix="/api", tags=["Leads"])
app.include_router(jobs.router, prefix="/api", tags=["Jobs"])
app.include_router(files.router, tags=["Files"])
app.include_router(converter.router, tags=["Converter"])

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Initializing database...")
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web UI"""
    html_path = Path("app/static/index.html")
    if html_path.exists():
        return html_path.read_text()
    return """
    <html>
        <body>
            <h1>Genealogy Lead Finder</h1>
            <p>Frontend not found. Please check app/static/index.html</p>
        </body>
    </html>
    """


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/init-db")
async def initialize_database():
    """Manually initialize database tables - for troubleshooting"""
    try:
        from app.database import Base, engine
        from app import models  # Import all models
        from app.models import person, address, relationship, source, processing_job, match_candidate

        Base.metadata.create_all(bind=engine)
        return {"status": "success", "message": "Database tables created"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.websocket("/ws/progress")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time progress updates"""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/load-all")
async def load_all_data(db: Session = Depends(get_db)):
    """Load all JSON files from sample_data/ and process them"""
    from app.schemas import IngestRequest
    from app.models import Source, ProcessingJob
    from app.tasks.celery_tasks import process_records_task
    from pathlib import Path

    sample_data_dir = Path("sample_data")
    if not sample_data_dir.exists():
        return {"error": "sample_data directory not found"}

    # Get all JSON files
    json_files = list(sample_data_dir.glob("*.json"))

    if not json_files:
        return {"error": "No JSON files found"}

    # Load each file directly
    job_ids = []

    for file_path in json_files:
        try:
            with open(file_path) as f:
                data = json.load(f)

            # Infer source type
            source_type = infer_source_type(file_path.name)

            # Store each record as a source
            source_ids = []
            for record in data.get("records", []):
                source = Source(
                    source_type=source_type,
                    file_name=file_path.name,
                    record_data=record
                )
                db.add(source)
                db.flush()
                source_ids.append(source.id)

            # Create processing job
            job = ProcessingJob(
                job_type="ingest_and_process",
                status="pending",
                total_records=len(data.get("records", [])),
                result_data={"source_ids": source_ids, "file_name": file_path.name}
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            job_ids.append(job.id)

            # Queue Celery task
            process_records_task.delay(job.id, source_ids, source_type)

            # Broadcast progress
            await manager.broadcast({
                "file": file_path.name,
                "status": "submitted",
                "progress": 0
            })

            # Log
            logger.info(f"Submitted {file_path.name} for processing (job {job.id})")

        except Exception as e:
            logger.error(f"Error loading {file_path.name}: {e}")
            await manager.broadcast({
                "file": file_path.name,
                "status": "error",
                "error": str(e)
            })

    # Monitor jobs and broadcast progress
    asyncio.create_task(monitor_jobs(job_ids, db))

    return {"message": f"Processing {len(job_ids)} files", "job_ids": job_ids}


async def monitor_jobs(job_ids: list, db: Session):
    """Monitor job progress and broadcast updates"""
    total_jobs = len(job_ids)
    completed_jobs = set()

    while len(completed_jobs) < total_jobs:
        for job_id in job_ids:
            if job_id in completed_jobs:
                continue

            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            if job and job.status in ["completed", "failed"]:
                completed_jobs.add(job_id)
                await manager.broadcast({
                    "job_id": job_id,
                    "file": job.file_name,
                    "status": job.status,
                    "progress": 100
                })
                logger.info(f"Job {job_id} ({job.file_name}) {job.status}")

        if len(completed_jobs) >= total_jobs:
            # Get final lead count
            leads_count = db.query(Person).filter(
                Person.birth_country == "Germany"
            ).count()

            await manager.broadcast({
                "status": "complete",
                "leads_count": leads_count
            })
            logger.info(f"All jobs complete. Found {leads_count} leads.")
            break

        await asyncio.sleep(2)

    db.close()


@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    db = next(get_db())

    try:
        total_records = db.query(Source).count()
        unique_persons = db.query(Person).count()
        leads_count = db.query(Person).filter(
            Person.birth_country == "Germany"
        ).count()

        dedup_rate = 0
        if total_records > 0:
            dedup_rate = round((1 - unique_persons / total_records) * 100, 1)

        return {
            "total_records": total_records,
            "unique_persons": unique_persons,
            "leads_count": leads_count,
            "dedup_rate": f"{dedup_rate}%"
        }
    finally:
        db.close()


def infer_source_type(filename: str) -> str:
    """Infer source type from filename"""
    filename_lower = filename.lower()
    if "natural" in filename_lower:
        return "naturalization"
    elif "immig" in filename_lower:
        return "immigration"
    elif "census" in filename_lower:
        return "census"
    elif "obit" in filename_lower:
        return "obituary"
    elif "birth" in filename_lower:
        return "birth"
    return "naturalization"  # default


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

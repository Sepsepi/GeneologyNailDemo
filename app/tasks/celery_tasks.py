"""Celery background tasks for processing genealogy records"""
from celery import Celery
from app.config import get_settings
from app.database import SessionLocal
from app.models import Source, RawPersonRecord, ProcessingJob, Person, Address, Relationship
from app.services.normalizer import DataNormalizer
from app.services.deduplicator import Deduplicator
from datetime import datetime
from typing import List

settings = get_settings()

# Initialize Celery
celery_app = Celery(
    "genealogy_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend
)

celery_app.conf.task_routes = {
    "app.tasks.celery_tasks.*": {"queue": "genealogy"}
}


@celery_app.task(name="process_records_task")
def process_records_task(job_id: int, source_ids: List[int], source_type: str):
    """
    Background task to process ingested records:
    1. Normalize data
    2. Create raw person records
    3. Deduplicate persons
    4. Extract relationships
    5. Extract addresses
    """
    db = SessionLocal()

    try:
        # Update job status
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            return {"error": "Job not found"}

        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        # Process each source
        persons_created = 0
        persons_merged = 0
        addresses_created = 0
        relationships_created = 0

        for source_id in source_ids:
            source = db.query(Source).filter(Source.id == source_id).first()
            if not source:
                continue

            # Normalize based on source type
            if source_type == "naturalization":
                normalized = DataNormalizer.normalize_naturalization_record(source.record_data)
                persons_data = [normalized]

                # Extract and store address
                if normalized.get("residence"):
                    # Will link after person creation
                    pass

            elif source_type == "immigration":
                normalized = DataNormalizer.normalize_immigration_record(source.record_data)
                persons_data = [normalized]

            elif source_type == "census":
                # Census has multiple household members
                persons_data = []
                address = source.record_data.get("address", "")
                for member in source.record_data.get("household_members", []):
                    normalized = DataNormalizer.normalize_census_household_member(member, address)
                    persons_data.append(normalized)

            elif source_type == "obituary":
                normalized = DataNormalizer.normalize_obituary_record(source.record_data)
                persons_data = [normalized]

                # Extract relationships from survivors/predeceased
                # (Simplified for now)

            elif source_type == "birth":
                normalized = DataNormalizer.normalize_birth_record(source.record_data)
                persons_data = [normalized]

                # Extract parent relationships
                # (Simplified for now)

            else:
                continue

            # Create raw person records
            for person_data in persons_data:
                raw_record = RawPersonRecord(
                    source_id=source.id,
                    normalized_data=person_data,
                    processed=False
                )
                db.add(raw_record)
                db.flush()

                # Deduplicate and match
                deduplicator = Deduplicator(db)
                person = deduplicator.process_record(raw_record)

                if raw_record.matched_person_id == person.id:
                    # Check if new person or merged
                    if person.id not in [p.id for p in db.query(Person).filter(Person.id < person.id).all()]:
                        persons_created += 1
                    else:
                        persons_merged += 1

                # Create address if available
                address_str = person_data.get("residence") or person_data.get("last_residence")
                if address_str and person.id:
                    # Simple address parsing
                    address = Address(
                        person_id=person.id,
                        street=address_str.split(',')[0] if ',' in address_str else address_str,
                        city=address_str.split(',')[1].strip() if len(address_str.split(',')) > 1 else None,
                        state=address_str.split(',')[2].strip() if len(address_str.split(',')) > 2 else None,
                        source_id=source.id
                    )
                    db.add(address)
                    addresses_created += 1

                job.records_processed += 1
                db.commit()

        # Mark job complete
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.result_data = {
            "persons_created": persons_created,
            "persons_merged": persons_merged,
            "addresses_created": addresses_created,
            "relationships_created": relationships_created
        }
        db.commit()

        return {
            "status": "success",
            "persons_created": persons_created,
            "persons_merged": persons_merged
        }

    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()
        db.commit()
        return {"status": "error", "message": str(e)}

    finally:
        db.close()

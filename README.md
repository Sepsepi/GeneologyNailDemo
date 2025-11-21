# Genealogy Data Pipeline

Backend system for processing genealogy records with fuzzy entity resolution and lead identification.

## System Overview

Ingests genealogy records from multiple sources, performs deduplication using fuzzy matching, and identifies persons with German ancestry for citizenship consulting.

**Core Capabilities:**
- RESTful API for data ingestion and lead retrieval
- Fuzzy matching deduplication (handles name variations like Franz → Francis → Frank)
- Background processing with Celery for async data handling
- Lead scoring (0-100 points) based on data quality and completeness
- Web interface for testing and visualization (optional)
- AI-powered file conversion (CSV/Excel/TXT → JSON)

## Tech Stack

- **Backend**: FastAPI + Python 3.11
- **Database**: PostgreSQL 15 with SQLAlchemy ORM
- **Task Queue**: Celery + Redis
- **Matching**: RapidFuzz (Levenshtein distance)
- **AI**: DeepSeek API (file conversion)
- **Frontend**: Vanilla JS + Tailwind CSS (optional demo)
- **Deployment**: Docker + docker-compose

## Quick Start

**Prerequisites:** Docker Desktop running

```bash
# Start all services
docker-compose up -d

# Access web interface (optional demo tool)
open http://localhost:8001/

# Or use API directly
curl http://localhost:8001/api/leads
```

**Default Port:** 8001 (API + Web UI)

## Database Schema

**7 Tables:**

1. **persons** - Deduplicated master records
2. **raw_person_records** - Pre-deduplication records
3. **relationships** - Family connections (parent/child/spouse/sibling)
4. **addresses** - Time-based residence tracking
5. **sources** - Original JSON records (JSONB, immutable)
6. **processing_jobs** - ETL audit trail
7. **match_candidates** - Fuzzy match review queue (70-89% similarity)

## Core API Endpoints

### POST /api/ingest
Ingest genealogy records. Returns job ID for async processing.

```bash
curl -X POST http://localhost:8001/api/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "naturalization",
    "file_name": "records.json",
    "records": [
      {
        "record_id": "NAT-1952-0847",
        "petitioner_name": "Franz Heinrich Mueller",
        "birth_date": "1925-03-15",
        "birth_place": "Munich, Bavaria, Germany",
        "naturalization_date": "1952-07-20"
      }
    ]
  }'
```

**Source Types:** `naturalization`, `immigration`, `census`, `obituary`, `birth`

### GET /api/leads
Retrieve citizenship leads with German ancestry.

```bash
curl "http://localhost:8001/api/leads?min_score=70&limit=50"
```

**Query Parameters:**
- `min_score` (default: 70) - Minimum lead quality score
- `has_german_ancestor` (default: true) - Filter for German ancestry
- `limit` (default: 50) - Max results

**Response:**
```json
[
  {
    "person_id": 1,
    "name": "Robert Franz Miller",
    "last_known_address": "3847 N Milwaukee Ave, Chicago, IL",
    "german_ancestor": {
      "name": "Franz Mueller",
      "birth_place": "Munich, Bavaria, Germany",
      "birth_date": "1925-03-15",
      "naturalization_date": "1952-07-20",
      "citizenship_eligible": true
    },
    "lead_score": 92,
    "data_confidence": "high",
    "sources_count": 5
  }
]
```

### GET /api/stats
System statistics (total records, persons, deduplication rate).

### GET /api/jobs/{job_id}
Check background job status.

### POST /api/load-all
Load all JSON files from `sample_data/` directory (batch processing).

## Web Interface (Optional)

Access: `http://localhost:8001/`

**Features:**
- File management (upload/download/delete JSON files)
- Preview JSON data in modal
- Batch processing ("Load All Data" button)
- Real-time WebSocket progress updates
- Leads table with expandable details
- Statistics dashboard
- Terminal-style logs
- CSV export

**AI File Conversion:**
- Upload CSV, Excel (XLSX), or TXT files
- System automatically converts to JSON format
- Detects record type (naturalization/immigration/census/obituary/birth)
- Normalizes dates and field names
- Handles messy data formats

**Note:** Web UI is a demo/testing tool. Backend API works standalone for integration with your own dashboards.

## Fuzzy Matching Algorithm

Multi-field weighted scoring:

```
Total Score = (
    Name Similarity × 40% +
    Birth Date Proximity × 30% +
    Birth Place Similarity × 20% +
    Birth Country Match × 10%
)
```

**Thresholds:**
- **≥90%**: Auto-merge (high confidence)
- **70-89%**: Manual review queue
- **<70%**: Separate persons

**Name Matching:**
- Token sort ratio for word order variations
- Handles Americanization (Franz → Francis → Frank)
- Phonetic similarity

**Date Proximity:**
- ±2 years tolerance (configurable)
- Linear decay scoring
- Handles partial/missing dates

## Lead Scoring

Leads scored 0-100 based on:

| Criterion | Points |
|-----------|--------|
| Has German-born ancestor | 25 |
| Multiple source verification (3+) | 20 |
| Complete family tree (3+ relationships) | 15 |
| Recent address available | 15 |
| Multiple addresses tracked | 10 |
| Living descendant (no death date) | 10 |
| Complete dates (no gaps) | 5 |

**Confidence Levels:**
- **High**: Score ≥80 + 3+ sources
- **Medium**: Score ≥60 + 2+ sources
- **Low**: Below medium threshold

## Sample Data

**5 JSON files with 50 records:**

1. `naturalization_records.json` (12 records) - U.S. citizenship petitions
2. `immigration_records.json` (12 records) - Port arrival manifests
3. `census_records.json` (8 records) - Household census data
4. `obituary_records.json` (8 records) - Death notices with family info
5. `birth_records.json` (10 records) - Birth certificates showing parentage

**Load Sample Data:**
```bash
# Via web interface
open http://localhost:8001/
# Click "Load All Data"

# Or via API
curl -X POST http://localhost:8001/api/load-all
```

## Configuration

**Environment Variables** (`.env`):
```bash
DATABASE_URL=postgresql://genealogy_user:genealogy_pass@db:5432/genealogy_db
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
DEEPSEEK_API_KEY=your_api_key_here  # For AI file conversion
```

**Matching Thresholds** (`app/config.py`):
```python
name_match_threshold = 0.85
auto_merge_threshold = 0.90
manual_review_threshold = 0.70
date_proximity_years = 2
```

## Architecture

```
┌─────────────┐
│   FastAPI   │  ← REST API + Web UI
└─────┬───────┘
      │
      ├─── POST /api/ingest  → Celery Queue
      │
      └─── GET /api/leads    → PostgreSQL
               │
               v
    ┌──────────────────┐
    │  Celery Workers  │  ← Background processing
    └──────────────────┘
               │
               ├─ Normalize data (dates, names, addresses)
               ├─ Fuzzy matching (RapidFuzz)
               ├─ Deduplication (merge/create persons)
               └─ Extract relationships (family tree)
               │
               v
    ┌──────────────────┐
    │   PostgreSQL     │  ← 7-table normalized schema
    └──────────────────┘
```

## Development

**Local Setup (without Docker):**

```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis
docker-compose up -d db redis

# Run API server
uvicorn app.main:app --reload --port 8001

# Run Celery worker (separate terminal)
celery -A app.tasks.celery_tasks worker --loglevel=info
```

**Testing:**

```bash
# Full automated test
./RUN_COMPLETE_TEST.sh

# Manual API test
curl http://localhost:8001/api/leads | python3 -m json.tool

# Database access
docker-compose exec db psql -U genealogy_user -d genealogy_db

# View logs
docker-compose logs api
docker-compose logs celery_worker

# Stop services
docker-compose down
```

## API Documentation

Interactive Swagger UI: `http://localhost:8001/docs`

Alternative ReDoc: `http://localhost:8001/redoc`

See `API_REFERENCE.md` for detailed endpoint documentation.

## Production Deployment

**Scaling Recommendations:**
- Horizontally scale Celery workers for throughput
- PostgreSQL read replicas for lead queries
- Redis caching for frequent lookups
- Batch processing (1000+ records per job)

**Monitoring:**
- Track job success/failure rates
- Monitor match quality (review queue size)
- Alert on processing delays
- Dashboard for lead pipeline metrics

**Security:**
- Add API authentication (JWT)
- Implement rate limiting
- Use HTTPS in production
- Enable PostgreSQL SSL
- Audit logging for data access

## Project Structure

```
genealogy/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration
│   ├── database.py             # SQLAlchemy setup
│   ├── models/                 # Database models
│   ├── schemas/                # Pydantic schemas
│   ├── api/endpoints/          # API routes
│   ├── services/               # Business logic
│   │   ├── normalizer.py       # Data normalization
│   │   ├── matcher.py          # Fuzzy matching
│   │   ├── deduplicator.py     # Person deduplication
│   │   ├── lead_scorer.py      # Lead scoring
│   │   └── file_converter.py   # AI file conversion
│   ├── tasks/                  # Celery tasks
│   └── static/                 # Web UI (optional)
│       ├── index.html
│       └── app.js
├── sample_data/                # Sample JSON files
├── docker-compose.yml          # Docker services
├── requirements.txt            # Python dependencies
└── README.md
```

## License

MIT

## Support

**API Documentation:** `http://localhost:8001/docs`

**Issues:** Check Docker logs if services fail to start
```bash
docker-compose logs api
docker-compose logs celery_worker
docker-compose logs db
```

**Common Issues:**
- Port 8001 in use: Change port in `docker-compose.yml`
- Database connection fails: Wait 10 seconds after `docker-compose up`
- Celery not processing: Check Redis connection in logs

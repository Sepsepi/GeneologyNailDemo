# API Reference

## Base URL
```
http://localhost:8001
```

## Authentication
None (test environment). Add JWT authentication for production.

---

## Endpoints

### Health Check
```
GET /health
```

**Response:**
```json
{
  "status": "healthy"
}
```

---

### Ingest Records
```
POST /api/ingest
```

Submit genealogy records for processing. Records are queued for background processing via Celery.

**Request Body:**
```json
{
  "source_type": "naturalization",
  "file_name": "nat_records.json",
  "records": [
    {
      "record_id": "NAT-1952-0847",
      "petitioner_name": "Franz Mueller",
      "birth_date": "1925-03-15",
      "birth_place": "Munich, Germany",
      "naturalization_date": "1952-07-20"
    }
  ]
}
```

**Source Types:**
- `naturalization` - Citizenship petitions
- `immigration` - Port arrival manifests
- `census` - Household census records
- `obituary` - Death notices
- `birth` - Birth certificates

**Response:**
```json
{
  "job_id": 1,
  "message": "Successfully queued 1 records for processing",
  "records_submitted": 1,
  "status": "pending"
}
```

**curl Example:**
```bash
curl -X POST http://localhost:8001/api/ingest \
  -H "Content-Type: application/json" \
  -d @sample_data/naturalization_records.json
```

---

### Get Leads
```
GET /api/leads
```

Retrieve citizenship eligibility leads filtered by score and ancestry.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_score` | integer | 70 | Minimum lead score (0-100) |
| `has_german_ancestor` | boolean | true | Filter for German ancestry |
| `limit` | integer | 50 | Maximum results (max 100) |

**Response:**
```json
[
  {
    "person_id": 2,
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

**curl Examples:**
```bash
# All leads (score >= 70)
curl http://localhost:8001/api/leads

# High-quality leads only
curl "http://localhost:8001/api/leads?min_score=85"

# Top 10 leads
curl "http://localhost:8001/api/leads?min_score=50&limit=10"
```

---

### Get Specific Lead
```
GET /api/leads/{person_id}
```

Retrieve details for a specific person.

**Response:** Same format as leads list, single object.

**curl Example:**
```bash
curl http://localhost:8001/api/leads/1
```

---

### Check Job Status
```
GET /api/jobs/{job_id}
```

Monitor background processing job status.

**Response:**
```json
{
  "job_id": 1,
  "job_type": "ingest_and_process",
  "status": "completed",
  "records_processed": 4,
  "total_records": 4,
  "result_data": {
    "persons_created": 8,
    "persons_merged": 3,
    "addresses_created": 11
  },
  "started_at": "2025-01-15T10:30:00",
  "completed_at": "2025-01-15T10:30:05"
}
```

**Status Values:**
- `pending` - Queued, not started
- `running` - Currently processing
- `completed` - Successfully finished
- `failed` - Error occurred (see `error_message`)

**curl Example:**
```bash
curl http://localhost:8001/api/jobs/1
```

---

### Get Statistics
```
GET /api/stats
```

System statistics: total records, unique persons, leads count, deduplication rate.

**Response:**
```json
{
  "total_records": 272,
  "unique_persons": 48,
  "leads_count": 20,
  "dedup_rate": "82.4%"
}
```

---

### Batch Load All Files
```
POST /api/load-all
```

Load and process all JSON files in `sample_data/` directory. Creates jobs for each file.

**Response:**
```json
{
  "message": "Processing 5 files",
  "job_ids": [1, 2, 3, 4, 5]
}
```

---

### File Management Endpoints

#### List Files
```
GET /api/files
```

List all JSON files in `sample_data/` directory.

**Response:**
```json
[
  {
    "name": "naturalization_records.json",
    "records": 12,
    "type": "naturalization"
  }
]
```

#### Get File Contents
```
GET /api/files/{filename}
```

Retrieve file contents.

#### Download File
```
GET /api/files/{filename}/download
```

Download file.

#### Upload File
```
POST /api/files/upload
```

Upload JSON, CSV, XLSX, or TXT file. Non-JSON files are automatically converted using AI.

**Request:** `multipart/form-data` with `file` field

**Response (JSON upload):**
```json
{
  "message": "File uploaded successfully",
  "filename": "records.json",
  "converted": false
}
```

**Response (CSV/XLSX/TXT upload with AI conversion):**
```json
{
  "message": "File converted and saved as records.json",
  "filename": "records.json",
  "converted": true,
  "record_type": "immigration",
  "records_count": 4
}
```

#### Delete File
```
DELETE /api/files/{filename}
```

Delete file from `sample_data/` directory.

---

## WebSocket

### Real-time Progress Updates
```
WS /ws/progress
```

WebSocket connection for real-time job progress updates.

**Message Format:**
```json
{
  "file": "naturalization_records.json",
  "status": "submitted|completed|failed",
  "progress": 100
}
```

**Completion Message:**
```json
{
  "status": "complete",
  "leads_count": 20
}
```

---

## Response Fields

### Lead Response

| Field | Type | Description |
|-------|------|-------------|
| `person_id` | integer | Unique person identifier |
| `name` | string | Full name (deduplicated) |
| `last_known_address` | string | Most recent address on record |
| `german_ancestor.name` | string | Name of German-born ancestor |
| `german_ancestor.birth_place` | string | Birthplace in Germany |
| `german_ancestor.birth_date` | string | Birth date (YYYY-MM-DD) |
| `german_ancestor.naturalization_date` | string | Naturalization date (YYYY-MM-DD) |
| `german_ancestor.citizenship_eligible` | boolean | Eligibility flag |
| `lead_score` | integer | Quality score 0-100 |
| `data_confidence` | string | "high", "medium", or "low" |
| `sources_count` | integer | Number of source records |

### Score Interpretation

| Score Range | Confidence | Description |
|-------------|------------|-------------|
| 85-100 | High | Excellent lead, multiple sources |
| 70-84 | Medium | Good lead, some verification |
| 50-69 | Low | Possible lead, needs review |
| 0-49 | Very Low | Weak lead, incomplete data |

---

## Error Responses

### 404 Not Found
```json
{
  "detail": "Person not found"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "records"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Server Error
```json
{
  "detail": "Internal server error message"
}
```

---

## Common Workflows

### Workflow 1: Load Data & Get Leads
```bash
# 1. Submit records
curl -X POST http://localhost:8001/api/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "naturalization",
    "file_name": "test.json",
    "records": [...]
  }'

# Response: {"job_id": 1, ...}

# 2. Wait for processing
sleep 5

# 3. Get leads
curl http://localhost:8001/api/leads?min_score=70
```

### Workflow 2: Monitor Processing
```bash
# Start ingestion
JOB_ID=$(curl -s -X POST http://localhost:8001/api/ingest \
  -H "Content-Type: application/json" \
  -d @sample_data/census_records.json \
  | jq -r '.job_id')

# Poll status
while true; do
  STATUS=$(curl -s http://localhost:8001/api/jobs/$JOB_ID | jq -r '.status')
  echo "Job $JOB_ID: $STATUS"
  [ "$STATUS" = "completed" ] && break
  sleep 2
done

echo "Processing complete!"
```

### Workflow 3: Find Best Leads
```bash
# Get top 5 highest-scoring leads
curl -s "http://localhost:8001/api/leads?min_score=80&limit=5" \
  | jq '.[] | {
      name: .name,
      score: .lead_score,
      ancestor: .german_ancestor.name,
      birthplace: .german_ancestor.birth_place
    }'
```

---

## Testing the API

### Using Python
```python
import requests

# Get leads
response = requests.get("http://localhost:8001/api/leads", params={
    "min_score": 80,
    "limit": 10
})
leads = response.json()

for lead in leads:
    print(f"{lead['name']}: {lead['lead_score']}/100")
```

### Using HTTPie
```bash
# Install: pip install httpie

# Get leads
http GET localhost:8001/api/leads min_score==85

# Post data
http POST localhost:8001/api/ingest < sample_data/naturalization_records.json
```

---

## Interactive Documentation

**Swagger UI:** `http://localhost:8001/docs`
- Try all endpoints interactively
- See full schemas
- No curl needed

**ReDoc:** `http://localhost:8001/redoc`
- Alternative documentation view
- Clean, readable format

---

## Rate Limiting

**Current:** No rate limiting (test environment)

**Production Recommendations:**
- `/api/ingest`: 10 requests/minute
- `/api/leads`: 60 requests/minute
- `/api/jobs`: 120 requests/minute
- `/api/files/*`: 30 requests/minute

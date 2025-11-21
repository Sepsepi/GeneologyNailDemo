# System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                             │
│  • curl/Python scripts (API access)                          │
│  • Web Browser (optional UI at localhost:8001)              │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/WebSocket
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  FASTAPI APPLICATION                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  REST API Endpoints                                   │  │
│  │  • POST /api/ingest       • GET /api/leads           │  │
│  │  • GET /api/stats         • POST /api/load-all       │  │
│  │  • GET /api/jobs/{id}     • WS /ws/progress          │  │
│  │  • GET /api/files         • POST /api/files/upload   │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Static File Server (optional)                        │  │
│  │  • Serves web UI (index.html + app.js)               │  │
│  │  • WebSocket manager for real-time updates           │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────┬────────────────────────────────────────────────┘
             │ Queue Tasks
             ▼
┌─────────────────────────────────────────────────────────────┐
│                    CELERY WORKERS                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Background Processing Pipeline                       │  │
│  │  1. Normalize Data      (dates, names, addresses)    │  │
│  │  2. Fuzzy Match Persons (RapidFuzz, 4-field scoring) │  │
│  │  3. Deduplicate         (merge/create persons)       │  │
│  │  4. Extract Relationships (family tree)              │  │
│  │  5. Score Leads         (0-100 point algorithm)      │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────┬────────────────────────────────────────────────┘
             │ Store/Retrieve
             ▼
┌─────────────────────────────────────────────────────────────┐
│                   POSTGRESQL DATABASE                        │
│  • persons               (deduplicated master records)       │
│  • raw_person_records    (pre-dedup normalized data)         │
│  • relationships         (parent/child/spouse/sibling)       │
│  • addresses             (time-based residence history)      │
│  • sources               (original JSON in JSONB)            │
│  • processing_jobs       (ETL audit trail)                   │
│  • match_candidates      (manual review queue 70-89%)        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        REDIS CACHE                           │
│  • Celery message broker                                     │
│  • Task result backend                                       │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow - Ingestion Pipeline

```
JSON Records (via API or Web Upload)
    │
    ▼
POST /api/ingest
    │
    ├─► Create Source record (store original JSON)
    │
    └─► Queue Celery task
            │
            ▼
    ┌───────────────────┐
    │  Normalize Data   │
    │  • Parse dates    │
    │  • Split names    │
    │  • Clean address  │
    └─────────┬─────────┘
              │
              ▼
    ┌────────────────────┐
    │ Create Raw Person  │
    │ Records            │
    └─────────┬──────────┘
              │
              │ For each record
              ▼
    ┌────────────────────┐
    │  Fuzzy Match       │
    │  Against Existing  │
    │  Persons           │
    └─────────┬──────────┘
              │
              ├─► Score ≥ 90% ────► Auto-merge
              │
              ├─► 70-89% ────────► Create match candidate
              │                    (manual review queue)
              │
              └─► < 70% ─────────► Create new person
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │  Update Person        │
                        │  • Merge data         │
                        │  • Add address        │
                        │  • Link source        │
                        │  • Extract relations  │
                        └───────────────────────┘
```

## Fuzzy Matching Algorithm

```
Person A vs Person B
    │
    ▼
┌─────────────────────────────────────────────┐
│  Compare Names (Weight: 40%)                │
│  Token sort ratio (RapidFuzz)               │
│  "Franz Heinrich Mueller" vs "Francis Miller"│
│  → Similarity: 0.85                          │
└─────────────┬───────────────────────────────┘
              ▼
┌─────────────────────────────────────────────┐
│  Compare Birth Dates (Weight: 30%)          │
│  Date proximity ±2 years tolerance          │
│  1925-03-15 vs 1925-03-14                   │
│  → Similarity: 0.99                          │
└─────────────┬───────────────────────────────┘
              ▼
┌─────────────────────────────────────────────┐
│  Compare Birth Places (Weight: 20%)         │
│  Fuzzy location match                        │
│  "Munich, Germany" vs "Munich, Bavaria"     │
│  → Similarity: 0.95                          │
└─────────────┬───────────────────────────────┘
              ▼
┌─────────────────────────────────────────────┐
│  Compare Birth Country (Weight: 10%)        │
│  Exact match required                        │
│  "Germany" vs "Germany"                      │
│  → Similarity: 1.0                           │
└─────────────┬───────────────────────────────┘
              ▼
┌─────────────────────────────────────────────┐
│  Weighted Total                              │
│  (0.85×0.4 + 0.99×0.3 + 0.95×0.2 + 1.0×0.1) │
│  = 0.927 = 92.7%                             │
└─────────────┬───────────────────────────────┘
              │
              ▼
        ┌──────────┐
        │  ≥ 90%?  │──YES──► Auto-merge
        └────┬─────┘
             │ NO
             ▼
        ┌──────────┐
        │  ≥ 70%?  │──YES──► Manual review queue
        └────┬─────┘
             │ NO
             ▼
      Create separate person
```

## Lead Scoring System

```
Person Record
    │
    ▼
Has German-born ancestor?
    │
    ├─ YES ────► +25 points
    │
    ▼
Count source records
    │
    ├─ 3+ sources ───► +20 points
    ├─ 2 sources ────► +10 points
    │
    ▼
Count relationships
    │
    ├─ 3+ relations ─► +15 points
    ├─ 1-2 relations ► +7 points
    │
    ▼
Has address?
    │
    ├─ YES ──────────► +15 points
    ├─ Multiple ─────► +10 points
    │
    ▼
Is living? (no death date)
    │
    ├─ YES ──────────► +10 points
    │
    ▼
Has complete dates?
    │
    ├─ YES ──────────► +5 points
    │
    ▼
┌──────────────┐
│  Total Score │
│  0-100       │
└──────┬───────┘
       │
       ▼
Determine Confidence Level
    │
    ├─ 80+ & 3+ sources ──► HIGH
    ├─ 60+ & 2+ sources ──► MEDIUM
    └─ Otherwise ─────────► LOW
```

## Web Interface Architecture (Optional Component)

```
┌──────────────────────────────────────────────┐
│           Browser (localhost:8001)            │
├──────────────────────────────────────────────┤
│  ┌────────────────────────────────────────┐ │
│  │  UI Components                          │ │
│  │  • File management (upload/download)   │ │
│  │  • Leads table (expandable details)    │ │
│  │  • Statistics dashboard                │ │
│  │  • Terminal logs (live output)         │ │
│  │  • JSON preview modal                  │ │
│  │  • Progress bars (processing status)   │ │
│  └────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────┐ │
│  │  Frontend Logic (app.js)                │ │
│  │  • Fetch API for REST calls            │ │
│  │  • WebSocket client for real-time      │ │
│  │  • State management                     │ │
│  │  • Event handlers                       │ │
│  └────────────────────────────────────────┘ │
└──────────┬────────────────────┬──────────────┘
           │ HTTP               │ WebSocket
           ▼                    ▼
    ┌─────────────┐    ┌─────────────────┐
    │ REST API    │    │ WS /ws/progress │
    └─────────────┘    └─────────────────┘
```

## AI File Conversion Flow

```
User uploads CSV/XLSX/TXT file
    │
    ▼
POST /api/files/upload
    │
    ├─► JSON file? ──► Validate & save
    │
    └─► CSV/XLSX/TXT?
            │
            ▼
    ┌──────────────────────┐
    │  Save to temp file   │
    └───────┬──────────────┘
            │
            ▼
    ┌──────────────────────┐
    │  Read file contents  │
    │  (pandas)            │
    └───────┬──────────────┘
            │
            ▼
    ┌──────────────────────┐
    │  DeepSeek AI         │
    │  • Detect type       │
    │  • Map fields        │
    │  • Normalize dates   │
    │  • Generate JSON     │
    └───────┬──────────────┘
            │
            ▼
    ┌──────────────────────┐
    │  Generate unique IDs │
    │  Format: TYPE-TIME-  │
    │  FILENAME-SEQNUM     │
    └───────┬──────────────┘
            │
            ▼
    ┌──────────────────────┐
    │  Save to            │
    │  sample_data/       │
    └───────┬──────────────┘
            │
            ▼
    Return: {filename, converted: true,
             record_type, records_count}
```

## Database Schema Relationships

```
┌──────────┐
│ sources  │────┐
│ (JSONB)  │    │
└──────────┘    │ 1:N
                ▼
        ┌────────────────────┐
        │ raw_person_records │
        │  (normalized)      │
        └─────────┬──────────┘
                  │ N:1
                  │ (matched_person_id)
                  ▼
             ┌─────────┐
             │ persons │◄───────┐
             │(deduped)│        │
             └────┬────┘        │
                  │             │
           ┌──────┴──────┐     │ N:1
           │             │     │
           ▼             ▼     │
    ┌───────────┐  ┌──────────────────┐
    │ addresses │  │  relationships   │
    │  (1:N)    │  │  • person_id     │
    └───────────┘  │  • related_id    │
                   │  • type          │
                   └──────────────────┘

┌─────────────────┐
│ processing_jobs │  (audit trail)
└─────────────────┘

┌──────────────────┐
│ match_candidates │  (70-89% matches)
└──────────────────┘
```

## Service Layer Components

```
┌──────────────────────────────────────────────┐
│              BUSINESS LOGIC LAYER             │
├──────────────────────────────────────────────┤
│                                               │
│  ┌──────────────────┐  ┌──────────────────┐ │
│  │  DataNormalizer  │  │  PersonMatcher   │ │
│  │                  │  │                  │ │
│  │ • Parse names    │  │ • Token sort     │ │
│  │ • Parse dates    │  │ • Date proximity │ │
│  │ • Parse address  │  │ • Weighted score │ │
│  │ • Standardize    │  │ • Thresholds     │ │
│  └──────────────────┘  └──────────────────┘ │
│                                               │
│  ┌──────────────────┐  ┌──────────────────┐ │
│  │  Deduplicator    │  │   LeadScorer     │ │
│  │                  │  │                  │ │
│  │ • Find matches   │  │ • Calculate pts  │ │
│  │ • Merge records  │  │ • Find ancestor  │ │
│  │ • Create persons │  │ • Confidence     │ │
│  │ • Link sources   │  │ • Business logic │ │
│  └──────────────────┘  └──────────────────┘ │
│                                               │
│  ┌──────────────────────────────────────┐   │
│  │  FileConverter (AI Integration)       │   │
│  │  • Read CSV/XLSX/TXT                  │   │
│  │  • DeepSeek API calls                 │   │
│  │  • Type detection                     │   │
│  │  • Generate unique record IDs         │   │
│  └──────────────────────────────────────┘   │
│                                               │
└──────────────────────────────────────────────┘
```

## Technology Stack Layers

```
┌─────────────────────────────────────────┐
│  DEPLOYMENT                              │
│  Docker, docker-compose                  │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│  APPLICATION                             │
│  FastAPI, Uvicorn, Celery               │
│  WebSockets (real-time updates)         │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│  BUSINESS LOGIC                          │
│  Services, Normalizers, Matchers         │
│  Scorers, DeepSeek AI Integration        │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│  DATA ACCESS                             │
│  SQLAlchemy ORM, Pydantic Schemas        │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│  PERSISTENCE                             │
│  PostgreSQL 15, Redis 7                  │
└─────────────────────────────────────────┘
```

## Deployment Architecture

### Current Setup (Docker Compose)
```
┌─────────────────────┐
│  FastAPI Container  │  Port 8001
│  • API server       │
│  • Web UI server    │
│  • WebSocket server │
└──────────┬──────────┘
           │
┌──────────┴──────────┐
│ Celery Worker       │
│ • Background jobs   │
└──────────┬──────────┘
           │
┌──────────┴──────────┐
│  PostgreSQL         │  Port 5432
│  • 7 tables         │
└─────────────────────┘

┌─────────────────────┐
│  Redis              │  Port 6379
│  • Task queue       │
│  • Result backend   │
└─────────────────────┘
```

### Production Scaling Strategy
```
                    ┌─► FastAPI Instance 1
                    │
Load Balancer ──────┼─► FastAPI Instance 2 ──► PostgreSQL Primary
                    │                                │
                    └─► FastAPI Instance 3           ├─► Read Replica 1
                                                     └─► Read Replica 2

                    ┌─► Celery Worker 1
Redis Cluster ──────┼─► Celery Worker 2
                    └─► Celery Worker 3
```

## WebSocket Real-Time Updates

```
Client connects to WS /ws/progress
    │
    ▼
User clicks "Load All Data"
    │
    ▼
POST /api/load-all
    │
    ├─► Create jobs for each file
    │
    └─► Broadcast: {file, status: "submitted"}
            │
            ▼
    Celery processes jobs
            │
            ├─► Job completes
            │
            └─► Broadcast: {file, status: "completed", progress: 100}
                    │
                    ▼
    All jobs complete
            │
            └─► Broadcast: {status: "complete", leads_count: N}
                    │
                    ▼
            Client auto-refreshes
            • Hides progress bars
            • Shows completion popup
            • Refreshes stats
            • Refreshes leads table
```

## Security Considerations

**Current (Test Environment):**
- No authentication
- No rate limiting
- HTTP only
- CORS enabled for all origins

**Production Recommendations:**
- JWT authentication on all endpoints
- Role-based access control
- Rate limiting per IP/user
- HTTPS enforcement
- PostgreSQL SSL connections
- Input sanitization (Pydantic handles this)
- SQL injection prevention (SQLAlchemy ORM)
- Audit logging for data access
- Environment-based configuration
- Secrets management (not in code)

## Performance Optimization Points

**Database:**
- Index on `(last_name, birth_date)` for fuzzy matching
- Partition `sources` table by `source_type`
- Read replicas for lead queries
- Connection pooling (pgBouncer)

**Caching:**
- Redis cache for frequent lead lookups
- Cache API responses (5 min TTL)
- Pre-compute high-score leads

**Processing:**
- Batch records (1000 per job)
- Parallel Celery workers
- Soundex pre-filtering for matching
- Early exit on low similarity scores

**API:**
- Pagination on leads endpoint
- Background jobs for large ingests
- Compress responses (gzip)
- CDN for static assets (web UI)

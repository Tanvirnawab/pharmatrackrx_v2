# PharmaTrackRx

Transfer verification, inward receiving, OCR review, and discrepancy management SaaS for pharmaceutical distributors.

PharmaTrackRx sits on top of AExpert and the existing inward workflow. It does not replace the stock system. It adds structure around verification: who received what, what was short or excess, what evidence was captured, and whether the discrepancy was resolved.

---

## What It Does

| Problem today | How PharmaTrackRx fixes it |
|---|---|
| Manager physically counts stock and compares against paper or Excel | Import the AExpert transfer sheet and verify received quantities against expected lines |
| Discrepancies are managed over WhatsApp with no trail | Auto-created discrepancy tickets assigned to the responsible depot |
| Multiple staff verify the same inward with no coordination | Multi-user inward sessions with assignment and progress visibility |
| Management has no visibility into shortage trends | Dashboard and reports for transfer accuracy, discrepancy medicines, and depot performance |
| No audit trail for who changed what | Append-only audit log for important state changes |
| Receiving documents are manually checked | V3 OCR Receiving stores uploaded documents, extracts candidate lines, matches them to transfer orders, and supports review/approval |

---

## Version Status

### V2 Core Platform

Implemented and preserved:

- Authentication and RBAC
- Multi-tenant architecture
- Transfer order Excel import
- Inward verification
- Multi-user inward assignment
- Progress tracking
- Discrepancy workflow
- Audit logging
- Notifications
- Dashboard and reports
- Docker Compose deployment
- PostgreSQL, Redis, MinIO, FastAPI, React/Vite, and Nginx

### V3 Smart Receiving OCR

Implemented foundation:

- OCR document upload from the frontend
- Original file storage through MinIO/S3-compatible storage
- OCR job queue using Redis
- Background OCR worker service
- OCR job, OCR result, and OCR match-result database tables
- OCR result matching against transfer order items
- OCR upload, job list, and review screens
- OCR approve/reject workflow
- Audit logs and notifications for OCR completion, approval, and rejection
- Approval path that creates or reuses an inward verification draft for the linked transfer order
- Tesseract OCR fallback
- PaddleOCR integration point prepared for environments that install PaddleOCR

Current V3 limitations:

- The current Docker flow uses Tesseract fallback. PaddleOCR is prepared but not fully wired as the runtime OCR engine.
- PDF uploads are accepted as uploaded files, but robust PDF page conversion before OCR is still pending.
- OCR correction editing is scaffolded through the API shape; the current review UI focuses on review, approve, and reject.
- LLM-assisted parsing for messy invoices is planned but not implemented yet.

### V4 AI Operations And Analytics

Existing analytics preserved:

- Dashboard summary metrics
- Discrepancy trends
- Top discrepant medicines
- Depot performance
- Average discrepancy resolution time

Planned V4 work not yet fully implemented:

- AI copilot for natural-language operational questions
- Predictive shortage, excess, expiry, and depot-risk alerts
- Advanced Excel, CSV, and PDF report exports
- Email notification delivery
- Role-specific enterprise dashboard views
- Weekly AI-generated operational summaries

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- 4 GB RAM minimum

### 1. Configure

```bash
cd pharma_v1_v2
cp backend/.env.example backend/.env
```

Edit `backend/.env` and change `SECRET_KEY`:

```env
SECRET_KEY=<output of: openssl rand -hex 32>
```

### 2. Start Everything

```bash
docker compose up -d
```

This starts:

- PostgreSQL on port `5432`
- Redis on port `6379`
- MinIO on ports `9000` and `9001`
- FastAPI backend on port `8000`
- OCR worker for background document processing
- React frontend on port `5173`
- Nginx reverse proxy on port `80`

### 3. Run Migrations

```bash
docker compose exec backend alembic upgrade head
```

### 4. First Login

On first start, PharmaTrackRx seeds a default admin user:

```text
Email:    admin@princepharma.com
Password: changeme123
```

Change this password immediately. Open `http://localhost/admin/users`, create proper users, then deactivate or change the default admin.

---

## Main Workflows

### Import Transfer Order

1. Export a Pending Stock Inward Report from AExpert as `.xlsx`.
2. Log in as admin or store manager.
3. Go to Transfer Orders.
4. Click Import Excel.
5. Upload the file.

### Start Inward Verification

1. Find the imported transfer order in the Pending tab.
2. Click Start.
3. Assign or share the session with store staff.
4. Staff enter received quantities and expiry dates.
5. The manager clicks Complete Inward.

Any variance automatically creates a discrepancy ticket.

### OCR Receiving

1. Go to OCR Receiving.
2. Upload a delivery note, invoice, GRN, transfer sheet, scanned image, or supported document file.
3. Link it to a transfer order when applicable.
4. The background worker processes OCR and matching.
5. Review extracted lines and confidence/match results.
6. Approve to create or reuse an inward verification draft, or reject with a reason.

---

## Architecture

```text
Browser (React + TypeScript + Vite)
        |
        | HTTPS + JWT
        v
FastAPI backend
  |-- REST API (/api/v1)
  |-- JWT auth + RBAC
  |-- Business service layer
  |-- Excel import engine
  |-- Inward verification workflow
  |-- OCR receiving API
  |-- Discrepancy workflow
  |-- Notification service
  `-- Analytics service
        |
        +--------------------+
        |                    |
        v                    v
PostgreSQL              Redis queue/cache
        |                    |
        v                    v
Core data, OCR tables   OCR worker
        |
        v
MinIO / S3-compatible file storage
```

Multi-tenancy: tenant-scoped data is enforced in service/API paths so one deployment can serve multiple distributors with data isolation.

No blocking: completing an inward session never waits for discrepancy approval. Actual received quantities are recorded immediately, and discrepancies run in parallel.

---

## Data Model

### Core Tables

| Table | Purpose |
|---|---|
| `tenants` | One row per pharma distributor |
| `users` | Users, roles, and store/depot scope |
| `depots` | Depot records imported or managed by the system |
| `stores` | Store records imported or managed by the system |
| `transfer_orders` | One per AExpert transfer number |
| `transfer_order_items` | Medicine lines in each transfer |
| `inward_sessions` | Verification session for a transfer order |
| `inward_session_participants` | Users working on an inward session |
| `inward_items` | Received quantity, expiry, and variance per item |
| `discrepancies` | Shortage/excess tickets |
| `discrepancy_comments` | Discussion thread per discrepancy |
| `discrepancy_attachments` | Evidence files linked to discrepancies |
| `audit_logs` | Append-only state-change records |
| `notifications` | In-app notifications |
| `file_uploads` | Metadata for uploaded files |
| `ocr_jobs` | Uploaded OCR document processing jobs |
| `ocr_results` | Extracted OCR candidate rows |
| `ocr_match_results` | Match/confidence records between OCR rows and transfer items |

### Variance Calculation

```text
variance = received_qty - expected_qty

variance < 0  => shortage discrepancy
variance > 0  => excess discrepancy
variance = 0  => match, no discrepancy
```

Variance is stored on every `inward_item` at write time.

---

## User Roles

| Role | Can do |
|---|---|
| `admin` | Everything: users, reports, resolve discrepancies, view all stores |
| `store_manager` | Start and complete inward sessions for their store, view store discrepancies |
| `store_staff` | Participate in sessions, update received quantities and expiry dates, add comments |
| `depot_staff` | View discrepancies for their depot and add depot responses |

---

## API Reference

Base URL: `http://localhost:8000/api/v1`

Interactive docs are available at `http://localhost:8000/docs` in development mode.

### Authentication

```text
POST /auth/login          { email, password } -> { access_token, refresh_token, user }
POST /auth/refresh        { refresh_token }   -> { access_token }
GET  /auth/me                                 -> user object
```

### Transfer Orders

```text
POST /transfer-orders/import     Upload .xlsx -> ImportResult
GET  /transfer-orders            Paginated list, filter by status/store/depot
GET  /transfer-orders/{id}       Detail with all line items
```

### Inward Verification

```text
POST /inward/start/{transfer_order_id}          Start session
GET  /inward/by-transfer/{transfer_order_id}    Resolve session for Continue links
GET  /inward/active                             Active sessions scoped by role
GET  /inward/{session_id}                       Session detail with all items
PUT  /inward/{session_id}/items/{id}            Update one item
PUT  /inward/{session_id}/items                 Batch update items
POST /inward/{session_id}/complete              Complete session and create discrepancies
```

### OCR Receiving

```text
POST /ocr/upload                  Upload document and enqueue OCR job
GET  /ocr/jobs                    OCR job list
GET  /ocr/job/{id}                OCR job detail
GET  /ocr/job/{id}/results        OCR results and match results
POST /ocr/job/{id}/approve        Approve OCR job and create/reuse inward draft
POST /ocr/job/{id}/reject         Reject OCR job with reason
```

### Discrepancies

```text
GET  /discrepancies                         Paginated list, filter by status/type/depot/store
GET  /discrepancies/{id}                    Detail with comments and attachments
POST /discrepancies/{id}/depot-response     Depot adds explanation
POST /discrepancies/{id}/resolve            Admin resolves/rejects/closes
POST /discrepancies/{id}/comments           Add comment
```

### Reports And Dashboard

```text
GET /dashboard/summary
GET /reports/discrepancy-trends
GET /reports/top-medicines
GET /reports/depot-performance
GET /reports/avg-resolution-time
```

---

## Development

### Backend Only

```bash
cd backend
python -m venv .venv
pip install -r requirements.txt
cp .env.example .env

docker compose up -d postgres redis minio
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend Only

```bash
cd frontend
npm install
npm run dev
```

### Worker Only

```bash
cd backend
python -m app.worker
```

### Run Tests

```bash
cd backend
pytest tests/ -v
```

---

## Database Migrations

PharmaTrackRx uses Alembic for schema migrations.

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "describe change"

# Roll back one migration
alembic downgrade -1
```

Current migrations:

| Revision | Purpose |
|---|---|
| `001_initial_schema` | Core V2 platform schema |
| `002_scanning_foundation` | Barcode/OCR-assisted inward scanning foundation |
| `003_ocr_foundation` | V3 OCR job/result/match tables and indexes |

Production deployment: always run `alembic upgrade head` before starting the backend.

---

## Docker Commands

```bash
# Start stack
docker compose up -d

# Check services
docker compose ps

# Apply migrations
docker compose exec backend alembic upgrade head

# View backend logs
docker compose logs -f backend

# View OCR worker logs
docker compose logs -f worker

# Rebuild after code changes
docker compose up -d --build
```

---

## Production Deployment

Recommended production setup:

- 4 vCPU / 8 GB RAM minimum
- Managed PostgreSQL
- Managed Redis or dedicated Redis service
- S3-compatible object storage such as DigitalOcean Spaces or MinIO
- HTTPS termination through Nginx, a load balancer, or platform proxy

Important environment values:

```env
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://user:pass@managed-db-host:5432/pharmatrackrx
REDIS_URL=redis://redis-host:6379/0
S3_ENDPOINT_URL=https://example-s3-endpoint
S3_ACCESS_KEY=<s3-key>
S3_SECRET_KEY=<s3-secret>
S3_BUCKET=pharmatrackrx-prod
SECRET_KEY=<openssl rand -hex 32>
ALLOWED_ORIGINS=https://pharmatrackrx.example.com
```

---

## Project Structure

```text
pharma_v1_v2/
|-- backend/
|   |-- app/
|   |   |-- api/v1/          # FastAPI routers, including OCR
|   |   |-- core/            # Config, security, dependencies
|   |   |-- db/              # SQLAlchemy base and session
|   |   |-- models/          # ORM models, including OCR tables
|   |   |-- schemas/         # Pydantic request/response models
|   |   |-- services/        # Business logic, OCR, storage, analytics
|   |   `-- worker.py        # Redis-backed OCR background worker
|   |-- alembic/             # Database migrations
|   `-- tests/               # pytest test suite
|-- frontend/
|   `-- src/
|       |-- api/             # Axios API modules
|       |-- components/      # UI primitives, layout, inward scanner widgets
|       |-- pages/           # Route pages, including OCR upload/jobs/review
|       |-- store/           # Zustand auth store
|       `-- utils/           # Formatters and helpers
|-- nginx/
|   `-- default.conf
|-- docker-compose.yml
|-- MERGE_REPORT.md
`-- README.md
```

---

## Roadmap

### V3 Next Steps

- Full PaddleOCR runtime support in Docker images
- PDF-to-image conversion before OCR
- Manual correction editor in the OCR review table
- Stronger invoice/GRN parsing for batch, expiry, pack size, and quantity extraction
- LLM-assisted parsing for messy supplier invoices

### V4 Next Steps

- KPI cards for today's inwards, pending inwards, completed inwards, shortages, excesses, active users, verification speed, and completion rate
- Charts for inward trends, discrepancy trends, depot performance, store performance, user productivity, and expiry risk
- AI copilot for natural-language operational questions
- Predictive alerts for repeated shortages, unusual excess quantities, expiry risks, depot performance issues, slow employee performance, and high-risk medicines
- Excel, CSV, and PDF export flows for operational reports
- Assignment, OCR-completed, discrepancy, expiry, and daily-summary notification upgrades
- Email notification delivery
- Role-specific enterprise dashboard views for admin, store manager, and store staff

---

## Key Design Decisions

Why not block inward completion on discrepancy approval?

Blocking inward completion would stop the store from updating actual stock. Discrepancies are tracked separately while the actual received quantity is recorded immediately.

Why Excel import instead of direct AExpert API?

AExpert export files are already available to depot and store teams. Direct sync can be added later without disrupting the proven workflow.

Why one inward session per transfer order?

A transfer order represents one physical dispatch. One verification session per dispatch keeps audit history clear and prevents double-counting.

Why store variance on every inward item?

Variance is computed once at write time and stored. This makes reports fast and preserves historical accuracy.

# PharmaTrackRx V1/V2 Merge Report

Target project: `pharma_v1_v2`

Source inputs:
- V1: `pharmatrackrx.zip`
- V2: `pharmatrackrx_v2.zip`

## Summary

V2 was used as the primary codebase. V1 did not contain any file paths that were missing from V2, so no source files were copied exclusively from V1. The merged project keeps the V2 feature set, including multi-user inward verification, employee assignments, progress tracking, discrepancy workflow, audit logging, dashboard, barcode/OCR/intelligence additions, migrations, and Docker setup.

## Files Changed In Merged Project

- `MERGE_REPORT.md` added.
- `frontend/package-lock.json` added by `npm install` for reproducible frontend installs.
- `frontend/src/vite-env.d.ts` added so TypeScript recognizes `import.meta.env`.
- `frontend/src/components/ui/index.tsx` updated so `Alert` accepts `className`, matching existing usage.
- `frontend/src/types/index.ts` updated with optional V2 scanner/OCR fields on `InwardItem`.
- Empty archive artifact directories were removed from the merged copy only:
  - `{backend,frontend,nginx}`
  - `backend/{app,alembic,tests}`
  - `backend/app/{core,db,models,schemas,services,api}`
  - `backend/tests/{api,services,data}`
  - `frontend/src/{api,store,types,utils,components,pages}`
  - `frontend/src/components/{layout,ui,inward,discrepancy}`
- Generated local artifacts were removed after verification:
  - `frontend/node_modules`
  - `frontend/dist`
  - `backend/.pytest_cache`
  - Python `__pycache__` directories

## Files Copied From V2

All retained application source was seeded from `pharmatrackrx_v2.zip`, including:
- `backend/app/**`
- `backend/alembic/**`
- `backend/entrypoint.sh`
- `backend/Dockerfile`
- `backend/requirements.txt`
- `frontend/src/**`
- `frontend/package.json`
- `frontend/Dockerfile`
- `docker-compose.yml`
- `nginx/default.conf`
- `README.md`

V2-only files preserved:
- `backend/alembic/versions/001_initial_schema.py`
- `backend/alembic/versions/002_v2_extensions.py`
- `backend/app/api/v1/scanning.py`
- `backend/app/api/v1/intelligence.py`
- `backend/app/models/batch_barcode.py`
- `backend/app/services/barcode_service.py`
- `backend/app/services/ocr_service.py`
- `backend/app/services/intelligence_service.py`
- `frontend/src/components/inward/BarcodeScanner.tsx`
- `frontend/src/components/inward/OCRCapture.tsx`
- `frontend/src/pages/Intelligence.tsx`

## Files Copied From V1

None. File comparison showed no V1-only paths missing from V2.

## Conflicts Resolved

- Common files differed between V1 and V2. V2 versions were kept because V2 is the requested primary codebase and contains the newer scanning, OCR, intelligence, routing, Docker entrypoint, and migration changes.
- Dependency differences:
  - V2 kept: `bcrypt`, `Pillow`, `pytesseract`, `@zxing/library`.
  - V1-only `celery` and `pytest-httpx` were not added because the merged code/tests do not reference them.
- Migrations:
  - V2 migration chain retained: `001_initial_schema.py` then `002_v2_extensions.py`.
  - Verified inside Docker Compose through `backend/entrypoint.sh`, which ran `alembic upgrade head`.
- Frontend type conflicts:
  - Added Vite env typing.
  - Added optional V2 scanner/OCR fields to `InwardItem`.
  - Allowed `Alert` to receive `className`, matching existing page usage.

## Verification Results

Passed:
- Backend Python syntax compile: `python -m compileall app`
- Alembic syntax compile: `python -m compileall alembic`
- Backend import with explicit env: `python -c "import app.main; print('backend import ok')"`
- Local backend health check: `GET http://127.0.0.1:8123/health` returned `200`
- Docker Compose config validation: `docker compose config`
- Docker Compose backend startup: passed
- Docker Compose migrations: passed
  - `Running upgrade  -> 001`
  - `Running upgrade 001 -> 002`
- Docker Compose backend health: `GET http://127.0.0.1:8000/health` returned `200`
- Frontend install: `npm install`
- Frontend production build: `npm run build`
- Docker Compose full stack startup: backend, postgres, redis, frontend, nginx running
- Frontend endpoint: `GET http://127.0.0.1:5173` returned `200`
- Nginx health proxy: `GET http://127.0.0.1/health` returned `200`

Notes:
- `docker compose config` warns that the `version` attribute is obsolete. It is harmless and was left unchanged to preserve the V2 Docker setup.
- Local host Alembic using `localhost:5432` hit a password mismatch outside the Compose network. Migrations were verified successfully through the backend container entrypoint against the Compose Postgres service.
- `npm install` reported two moderate audit findings. No forced upgrades were applied because that would change dependency versions beyond merge scope.

## Commands To Run

From `pharma_v1_v2`:

```powershell
docker compose up -d
```

Backend local setup:

```powershell
cd backend
python -m pip install -r requirements.txt
$env:DEBUG='false'
$env:SECRET_KEY='change-me'
$env:DATABASE_URL='postgresql+asyncpg://pharma:pharmasecret@127.0.0.1:5432/pharmatrackrx'
alembic upgrade head
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend local setup:

```powershell
cd frontend
npm install
npm run build
npm run dev -- --host
```

To stop the running Docker stack:

```powershell
docker compose down
```

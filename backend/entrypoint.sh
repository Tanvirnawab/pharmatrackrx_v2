#!/bin/bash
set -e

echo "========================================="
echo " PharmaTrackRx — starting up"
echo "========================================="

echo "[1/3] Waiting for database..."
until python -c "
import asyncio, asyncpg, sys
from app.core.config import settings

async def check():
    url = settings.sqlalchemy_database_url.replace('postgresql+asyncpg://', 'postgresql://')
    try:
        conn = await asyncpg.connect(url, **settings.asyncpg_connect_args)
        await conn.close()
        print('Database is ready.')
    except Exception as e:
        print(f'Waiting... {e}', file=sys.stderr)
        sys.exit(1)

asyncio.run(check())
" 2>/dev/null; do
    sleep 2
done

echo "[2/3] Running Alembic migrations..."
alembic upgrade head
echo "       Migrations complete."

echo "[3/3] Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000

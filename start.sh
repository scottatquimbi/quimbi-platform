#!/bin/bash
set -e

echo "Waiting for database to be ready..."
max_retries=30
counter=0

# Wait for database to be available
until python -c "
import asyncio
import sys
sys.path.insert(0, '/app')
from backend.core.database import init_db
try:
    asyncio.run(init_db())
    print('Database connection successful!')
except Exception as e:
    print(f'Database not ready: {e}')
    exit(1)
" 2>/dev/null; do
    counter=$((counter + 1))
    if [ $counter -gt $max_retries ]; then
        echo "❌ Database connection failed after $max_retries attempts"
        exit 1
    fi
    echo "⏳ Database not ready, waiting... ($counter/$max_retries)"
    sleep 2
done

echo "✅ Database is ready!"
echo "Running database migrations..."
alembic upgrade head

echo "Starting application..."
exec python -m backend.main

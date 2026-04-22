FROM python:3.11-slim

WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt ./backend-requirements.txt
RUN pip install --no-cache-dir -r backend-requirements.txt

# Install ETL dependencies (prod subset — no bigquery/basedosdados)
COPY etl/requirements-prod.txt ./etl-requirements.txt
RUN pip install --no-cache-dir -r etl-requirements.txt

# Copy backend source to /app
COPY backend/ /app/

# Copy ETL source to /app/etl (matches ETL_DIR in main.py)
COPY etl/ /app/etl/

# Use $PORT env var set by Railway (falls back to 8000 locally)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}

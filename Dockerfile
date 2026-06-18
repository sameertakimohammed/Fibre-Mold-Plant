# ---- Stage 1: build the React frontend ----
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend serving API + built frontend ----
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/data ./data
# Alembic migration tooling (config + revisions) and the startup entrypoint.
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY backend/entrypoint.sh ./entrypoint.sh
# Normalize potential CRLF (Windows host) to LF and make the script executable.
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh
# Copy built frontend from stage 1 into the path main.py serves
COPY --from=frontend /fe/dist ./static
EXPOSE 8000
# Readiness probe verifies the DB is reachable, not just that the process is up.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fs http://localhost:8000/api/health/ready || exit 1
ENTRYPOINT ["/app/entrypoint.sh"]

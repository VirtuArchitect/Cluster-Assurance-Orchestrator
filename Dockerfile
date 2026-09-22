# syntax=docker/dockerfile:1

FROM node:24-bookworm-slim AS frontend-build
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_API_BASE=
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CAO_ENVIRONMENT=appliance \
    CAO_DEMO_MODE=true \
    CAO_READ_ONLY_MODE=true \
    CAO_ENABLE_NCC=false \
    CAO_ENABLE_SSH=false \
    CAO_EVIDENCE_DIR=/data/evidence \
    CAO_ADMIN_DB_PATH=/data/cao-admin.sqlite3

WORKDIR /app
COPY pyproject.toml README.md ./
COPY backend ./backend
COPY --from=frontend-build /src/frontend/dist ./frontend/dist
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 cao \
    && mkdir -p /data/evidence \
    && chown -R cao:cao /data /app
USER cao

EXPOSE 8080
VOLUME ["/data"]
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8080"]

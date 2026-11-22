# syntax=docker/dockerfile:1

FROM node:24-bookworm-slim AS frontend-build
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
COPY backend/app/release.json /src/backend/app/release.json
ARG CAO_BUILD_REVISION=unknown
ARG CAO_BUILD_DATE=unknown
ARG CAO_SOURCE_STATE=unknown
ENV CAO_BUILD_REVISION=${CAO_BUILD_REVISION} CAO_BUILD_DATE=${CAO_BUILD_DATE} CAO_SOURCE_STATE=${CAO_SOURCE_STATE}
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
    CAO_ADMIN_DATABASE_URL=postgresql://cao:cao-local-dev-password@postgres:5432/cao

ARG CAO_BUILD_REVISION=unknown
ARG CAO_BUILD_DATE=unknown
ARG CAO_SOURCE_STATE=unknown
LABEL org.opencontainers.image.title="Cluster Assurance Orchestrator" \
    org.opencontainers.image.revision=${CAO_BUILD_REVISION} \
    org.opencontainers.image.created=${CAO_BUILD_DATE}
WORKDIR /app
COPY pyproject.toml README.md ./
COPY backend ./backend
COPY --from=frontend-build /src/frontend/dist ./frontend/dist
RUN python -c "import json; from pathlib import Path; Path('backend/app/build-info.json').write_text(json.dumps(dict(revision='${CAO_BUILD_REVISION}', built_at='${CAO_BUILD_DATE}', source_state='${CAO_SOURCE_STATE}')))"
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 cao \
    && mkdir -p /data/evidence \
    && chown -R cao:cao /data /app
USER cao

EXPOSE 8080
VOLUME ["/data"]
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8080"]

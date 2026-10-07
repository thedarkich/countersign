# Build from the repository root. Runtime credentials never enter build arguments.
FROM node:20-bookworm-slim AS frontend
ARG NPM_REGISTRY=https://registry.npmmirror.com
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --registry=$NPM_REGISTRY
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.12.23 AS uv
FROM python:3.11-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy \
    DATA_DIR=/app/data STATIC_DIR=/app/static \
    PATH=/app/backend/.venv/bin:$PATH
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY docs/deployments/ /app/docs/deployments/
COPY data/vendors.json data/pos.json /app/seed/
COPY --from=frontend /src/frontend/dist/ /app/static/
RUN groupadd --gid 10001 countersign && useradd --uid 10001 --gid 10001 --no-create-home countersign \
    && mkdir -p /app/data && chown 10001:10001 /app/data
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -m app.ops liveness
CMD ["python", "-m", "app.ops", "serve"]

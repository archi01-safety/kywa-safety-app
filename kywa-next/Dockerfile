FROM node:22-bookworm-slim AS frontend
WORKDIR /build
ENV NEXT_TELEMETRY_DISABLED=1
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=10000
RUN apt-get update && apt-get install -y --no-install-recommends fonts-nanum libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
RUN useradd --create-home --uid 10001 kywa && mkdir /app/local-data && chown kywa:kywa /app/local-data
COPY backend/ ./backend/
COPY --from=frontend /build/out ./frontend/out/
USER kywa
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --limit-concurrency 20 --timeout-keep-alive 5"]

FROM node:22-bookworm-slim AS frontend
WORKDIR /build
ENV NEXT_TELEMETRY_DISABLED=1
ARG APP_BASE_PATH=""
ENV APP_BASE_PATH=$APP_BASE_PATH
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=10000 HOST=0.0.0.0 APP_DATA_DIR=/app/local-data
ARG APP_BASE_PATH=""
ENV APP_BASE_PATH=$APP_BASE_PATH
RUN apt-get update && apt-get install -y --no-install-recommends fonts-nanum libglib2.0-0 libvips42 libheif1 libstdc++6 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
RUN useradd --create-home --uid 10001 kywa && mkdir /app/local-data && chown kywa:kywa /app/local-data
COPY backend/ ./backend/
COPY app.py ./app.py
RUN python -c "from pathlib import Path; from backend.photo_privacy import normalize_photo; assert normalize_photo(Path('backend/tests/fixtures/sample.heic').read_bytes()).startswith(b'\xff\xd8')"
COPY --from=frontend /build/out ./frontend/out/
COPY --from=frontend /usr/local/bin/node /usr/local/bin/node
USER kywa
EXPOSE 10000
CMD ["python", "app.py"]

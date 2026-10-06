# Root Dockerfile so hosting platforms (Render, Railway, Fly.io, Cloud Run, HF Spaces)
# can build without extra config. Serves the web API + demo site.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY code_archaeologist ./code_archaeologist
COPY site ./site
RUN pip install --no-cache-dir ".[web]"

RUN mkdir -p /app/data /app/.cache /app/archaeology-reports
ENV ARCHAEOLOGIST_ALLOWED_ROOT=/app/data \
    PYTHONUNBUFFERED=1 \
    PORT=8000

EXPOSE 8000
CMD ["sh", "-c", "uvicorn code_archaeologist.deploy.web_api:app --host 0.0.0.0 --port ${PORT:-8000}"]

# Build from the repository root:
#   docker build -f code_archaeologist/deploy/Dockerfile -t code-archaeologist .
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY code_archaeologist ./code_archaeologist
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["code-archaeologist"]
CMD ["--help"]

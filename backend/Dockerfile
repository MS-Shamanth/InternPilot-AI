# InternPilot AI backend image (design.md §18). Build context: ./backend
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/data

WORKDIR /app

# Unprivileged runtime user; the image ships no secrets and no .env file.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --home-dir /app app

COPY requirements.txt ./
RUN pip install --requirement requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
# Strip CR in case the script was checked out with CRLF before .gitattributes applied.
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod 0755 /usr/local/bin/docker-entrypoint.sh

USER app

EXPOSE 8000

# 200 only when the database answers; 503 (degraded) makes urlopen raise -> unhealthy.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]

ENTRYPOINT ["docker-entrypoint.sh"]

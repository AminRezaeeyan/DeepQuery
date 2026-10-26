# DeepQuery API and Celery worker (the same image runs both).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TIKTOKEN_CACHE_DIR=/data/tiktoken \
    MEDIA_ROOT=/data/media \
    STATIC_ROOT=/data/static

WORKDIR /app

# CPU-only PyTorch first (sentence-transformers needs it); the default wheel bundles CUDA.
COPY requirements.txt requirements-nodeps.txt ./
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r requirements.txt \
 && pip install --no-deps -r requirements-nodeps.txt

COPY . .

# Run as an unprivileged user; uploads, static files and caches live under /data.
RUN useradd --create-home --uid 1000 deepquery \
 && mkdir -p /data/media /data/static /data/tiktoken \
 && chown -R deepquery:deepquery /data /app \
 && chmod +x docker-entrypoint.sh
USER deepquery

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
# Threaded workers: an answer streams for minutes while the agent works.
CMD ["gunicorn", "deepquery.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--workers", "2", "--threads", "8", "--worker-class", "gthread", "--timeout", "900"]

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/data/huggingface \
    SQLITE_DB_PATH=/data/db.sqlite3 \
    MEDIA_ROOT=/data/media \
    CHROMA_DB_DIR=/data/chroma_db

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && python -m pip install -r requirements.txt

RUN groupadd --system app \
    && useradd --system --gid app --create-home app \
    && mkdir -p /data/media /data/chroma_db /data/huggingface \
    && chown -R app:app /data

COPY --chown=app:app . .

VOLUME ["/data"]
EXPOSE 8000
USER app

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000"]
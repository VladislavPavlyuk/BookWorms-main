FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-nas.txt /app/requirements-nas.txt
RUN pip install -r /app/requirements-nas.txt

# CACHEBUST ламає Docker layer cache після sync файлів на NAS.
ARG CACHEBUST=1
RUN echo "cachebust=${CACHEBUST}" > /tmp/cachebust

COPY bookworms/ /app/

COPY deploy/qnap/api/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && mkdir -p /app/media /app/staticfiles \
    && test -f /app/mainApp/middleware.py \
    && test -f /app/mainApp/migrations/0013_customuser_email_confirmed.py \
    && test -f /app/mainApp/migrations/0017_privatemessage_related_shelf.py \
    && test -f /app/mainApp/migrations/0018_bookcopy_shelf_copy.py \
    && test -f /app/mainApp/migrations/0019_copyevent.py \
    && grep -q 'code_rev' /app/api/views.py \
    && grep -q 'Cheap by default' /app/api/views.py \
    && grep -q post_worker_init /app/bookworms/gunicorn.conf.py \
    && ! grep -q 'purge loop every' /entrypoint.sh \
    && grep -q 'OL_HOST' /app/mainApp/openlibrary.py \
    && ! grep -q 'openlibrary.org/api/books' /app/mainApp/openlibrary.py

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements-fastapi.txt /app/requirements-fastapi.txt
RUN pip install -r /app/requirements-fastapi.txt

ARG CACHEBUST=1
RUN echo "cachebust=${CACHEBUST}" > /tmp/cachebust

COPY fastapi_app/ /app/fastapi_app/
COPY deploy/qnap/fastapi/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8001
ENTRYPOINT ["/entrypoint.sh"]

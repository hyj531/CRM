FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN if [ -f /etc/apt/sources.list ]; then \
        sed -i 's@deb.debian.org@mirrors.aliyun.com@g' /etc/apt/sources.list; \
        sed -i 's@security.debian.org@mirrors.aliyun.com@g' /etc/apt/sources.list; \
    elif [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's@deb.debian.org@mirrors.aliyun.com@g' /etc/apt/sources.list.d/debian.sources; \
        sed -i 's@security.debian.org@mirrors.aliyun.com@g' /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install -i https://mirrors.aliyun.com/pypi/simple --no-cache-dir -r /app/requirements.txt

FROM node:20-alpine AS frontend-build
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json /app/frontend/
RUN npm ci --prefix /app/frontend

COPY frontend /app/frontend
RUN mkdir -p /app/core/static/spa
RUN npm run build --prefix /app/frontend

FROM base AS runtime
WORKDIR /app

COPY . /app
COPY --from=frontend-build /app/core/static/spa /app/core/static/spa

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV DJANGO_DEBUG=0

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "crm.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]

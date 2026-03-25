#!/bin/sh
set -e

if [ "${DJANGO_SKIP_MIGRATE:-0}" != "1" ]; then
  python manage.py migrate --noinput
fi

if [ "${DJANGO_SKIP_COLLECTSTATIC:-0}" != "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"

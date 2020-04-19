#!/bin/bash

if [ "$1" == "app" ]; then
  exec gunicorn --bind=0.0.0.0:5000 --worker-class eventlet -w 1 --timeout 600 watchtogether.wsgi:app
fi

if [ "$1" == "workers" ]; then
  exec gunicorn --bind=0.0.0.0:5001 --worker-class eventlet -w 8 --timeout 600 watchtogether.wsgi:app
fi

if [ "$1" == "celery" ]; then
  exec celery -A watchtogether.tasks.celery worker --loglevel=info --concurrency=2
fi

exec bash

import os
import types
from pathlib import Path

TEMPLATES_AUTO_RELOAD = True
SECRET_KEY = os.getenv('SECRET_KEY', 'somethingsilly')
TITLE = os.getenv('TITLE', 'Watch Together!')
CELERY_BROKER_URL = 'redis://'
CELERY_RESULT_BACKEND = 'redis://'
MOVIE_PATH = os.getenv('MOVIE_PATH', 'watchtogether/static/movies')
STORAGE_BACKEND = os.getenv('STORAGE_BACKEND', 'files')
S3_BUCKET = os.getenv('S3_BUCKET', None)
S3_BUCKET_URL = os.getenv('S3_BUCKET_URL', None)
S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY', None)
S3_SECRET_KEY = os.getenv('S3_SECRET_KEY', None)
S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL', None)
S3_REGION = os.getenv('S3_REGION', None)
S3_UPLOAD_THREADS = int(os.getenv('S3_UPLOAD_THREADS', 20))
SQLALCHEMY_DATABASE_URI=os.getenv('SQLALCHEMY_DATABASE_URI', 'mysql://root:secret@127.0.0.1/watchtogether?charset=utf8mb4')
SQLALCHEMY_TRACK_MODIFICATIONS=False
COOKIE_OWNER_ID = os.getenv('COOKIE_OWNER_ID', 'owner_id')

def as_dict():
    d = {}

    for key, value in globals().copy().items():
        if not key.startswith('__') and not isinstance(value, (types.FunctionType, types.ModuleType)):
            d[key] = value

    return d

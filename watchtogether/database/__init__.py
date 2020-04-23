from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, create_session
from sqlalchemy.ext.declarative import declarative_base

from alembic.migration import MigrationContext

engine = None
db_session = scoped_session(
    lambda: create_session(bind=engine, autocommit=False))
Base = declarative_base()

db = SQLAlchemy()

def init_engine(uri):
    global engine

    engine = create_engine(uri, encoding='utf-8', convert_unicode=True, pool_pre_ping=True)
    return engine

def init_db():
    import os
    from . import models
    from alembic.config import Config
    from alembic import command

    connection = engine.connect()
    migration_context = MigrationContext.configure(connection)

    os.chdir('watchtogether')
    alembic_cfg = Config('alembic.ini')
    if not migration_context.get_current_revision():
        Base.query = db_session.query_property()
        Base.metadata.create_all(bind=engine)
        command.stamp(alembic_cfg, 'head')
    else:
        command.upgrade(alembic_cfg, 'head')
    os.chdir('..')

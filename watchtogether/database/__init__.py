from flask_sqlalchemy import SQLAlchemy
  
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, create_session
from sqlalchemy.ext.declarative import declarative_base

import traceback

engine = None
db_session = scoped_session(
    lambda: create_session(bind=engine, autocommit=False))
Base = declarative_base()

db = SQLAlchemy()

def init_engine(uri):
    global engine
    engine = create_engine(uri, encoding='utf-8', pool_pre_ping=True)
    return engine

def init_db():
    from . import models
    Base.query = db_session.query_property()
    Base.metadata.create_all(bind=engine)

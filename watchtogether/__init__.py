#!/usr/bin/env python3

import os
import sys
import time
import json

from flask import Flask, request, make_response
from werkzeug.contrib.fixers import ProxyFix
from flask_socketio import SocketIO

from watchtogether.database import init_db, db, init_engine
from watchtogether.config import settings
from watchtogether.api import flask_api

socketio = SocketIO()
rooms = {}

class Room:
    def __init__(self, name, video):
        self.name = name
        self.users = {}
        self.last = "system"
        self.messages = []
        self.video = video
        self.timer = Timer(video.duration)

    def join(self, sid, username):
        if username in self.users:
            self.users[username].append(sid)
            return False
        else:
            self.users[username] = [sid]
            return True

    def leave(self, sid):
        for username, sids in self.users.items():
            if sid in sids:
                sids.remove(sid)
                if len(sids) == 0:
                    self.users.pop(username, None)
                    return True
                else:
                    return False

        return False

    def message(self, username, text):
        message = f"<li><b>{username}: </b>{text}</li>"
        self.messages.append(message)
        return message

    def get_messages(self):
        return self.messages[-20:]

    def get_user_by_sid(self, sid):
        for username, sids in self.users.items():
            if sid in sids:
                return username
        return None

    def has_sid(self, sid):
        for username, sids in self.users.items():
            if sid in sids:
                return True
        return False

    def get_users(self):
        return list(self.users.keys())

class Timer:
    def __init__(self, end):
        self.time = 0
        self.end = float(end)
        self.last = time.monotonic()
        self.running = False

    def get(self):
        if self.running:
            now = time.monotonic()
            self.time = self.time + now - self.last
            self.last = now

            if self.time >= self.end:
                self.time = self.end
                self.running = False

        return self.time

    def set(self, value):
        self.last = time.monotonic()
        self.time = max(0, value)

    def start(self):
        if not self.running:
            self.last = time.monotonic()
            self.running = True

    def pause(self):
        self.time = self.get()
        self.running = False

    def reset(self):
        self.last = time.monotonic()
        self.time = 0

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object('watchtogether.config.settings')

    try:
        from flask_cors import CORS
        CORS(app)
    except ModuleNotFoundError:
        pass

    init_engine(settings.SQLALCHEMY_DATABASE_URI)
    db.init_app(app)
    init_db()

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    socketio.init_app(app)
    flask_api.init_app(app)

    from watchtogether.database import db_session

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()

    app.wsgi_app = ProxyFix(app.wsgi_app)
    return app


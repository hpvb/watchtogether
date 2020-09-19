#!/usr/bin/env python3

import json

from flask import Flask, render_template, request, make_response, redirect, abort
from flask import current_app as app

from watchtogether import rooms, tasks
from watchtogether.database import models, db_session
from watchtogether.auth import ownerid

from . import main

@main.route("/")
@ownerid
def index():
    return render_template("index.html")

@main.route("/videos/<video_id>", methods=["GET"])
@ownerid
def update_video(video_id):
    video = db_session.query(models.Video).filter_by(owner=owner_id, id=video_id).one_or_none()
    if not video:
        return make_response("Video not found", 404)
    
    if request.method == "GET":
        return render_template("video.html", video = video)

def get_chunk_name(uploaded_filename, chunk_number):
    return uploaded_filename + "_part_%03d" % chunk_number

@main.route("/watch/<video_id>", methods=["GET"])
@ownerid
def watch(video_id):
    video = db_session.query(models.Video).filter_by(id=video_id).one_or_none()

    if not video:
        abort(404, "Video not found")

    print("playlist: " + video.playlist)
    baseurl = "/static/movies/"
    if app.config['STORAGE_BACKEND'] == 'S3':
        baseurl = app.config['S3_BUCKET_URL']
        if not baseurl.endswith("/"):
            baseurl = baseurl + "/"
    
    return render_template("watch.html", baseurl = baseurl, video = video)

@main.route("/chat/<video_id>", methods=["GET"])
@ownerid
def chat(video_id):
    video = db_session.query(models.Video).filter_by(id=video_id).one_or_none()

    if not video:
        abort(404, "Video not found")

    return render_template("chat.html", video = video)

@main.route("/messages/<room>", methods=["GET"])
@ownerid
def get_messages(room):
    return "".join(rooms[room].get_messages())

@main.route("/users/<room>", methods=["GET"])
@ownerid
def get_users(room):
    return json.dumps(rooms[room].get_users())


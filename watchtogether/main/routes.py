#!/usr/bin/env python3

import os
import json

from flask import Flask, render_template, jsonify, request, make_response, redirect, abort
from flask import current_app as app

from watchtogether import rooms, tasks
from watchtogether.util import rm_f
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

@main.route("/videos/<video_id>/resumable_upload", methods=['GET'])
@ownerid
def resumable(video_id):
    video = db_session.query(models.Video).filter_by(owner=owner_id, id=video_id).one_or_none()
    if not video:
        return abort(403, "Video not found")

    resumableIdentfier = request.args.get('resumableIdentifier', type=str)
    resumableChunkNumber = request.args.get('resumableChunkNumber', type=int)

    if not resumableIdentfier or not resumableChunkNumber:
        # Parameters are missing or invalid
        abort(500, 'Parameter error')

    # chunk path based on the parameters
    chunk_file = os.path.join(app.config['MOVIE_PATH'], video_id, 'tmp', get_chunk_name('orig', resumableChunkNumber))
    app.logger.debug('Getting chunk: %s', chunk_file)

    if os.path.isfile(chunk_file):
        # Let resumable.js know this chunk already exists
        return 'OK'
    else:
        # Let resumable.js know this chunk does not exists and needs to be uploaded
        abort(404, 'Not found')

@main.route("/videos/<video_id>/resumable_upload", methods=['POST'])
@ownerid
def resumable_post(video_id):
    video = db_session.query(models.Video).filter_by(owner=owner_id, id=video_id).one_or_none()
    if not video:
        return abort(403, "Video not found")

    resumableTotalChunks = request.form.get('resumableTotalChunks', type=int)
    resumableChunkNumber = request.form.get('resumableChunkNumber', default=1, type=int)
    resumableIdentfier = request.form.get('resumableIdentifier', default='error', type=str)

    # get the chunk data
    chunk_data = request.files['file']

    # make our temp directory
    temp_dir = os.path.join(app.config['MOVIE_PATH'], video_id, 'tmp', resumableIdentfier)
    if not os.path.isdir(temp_dir):
        os.makedirs(temp_dir)

    # save the chunk data
    chunk_name = get_chunk_name('orig', resumableChunkNumber)
    chunk_file = os.path.join(temp_dir, chunk_name)
    chunk_data.save(chunk_file)
    app.logger.debug('Saved chunk: %s', chunk_file)

    # check if the upload is complete
    chunk_paths = [os.path.join(temp_dir, get_chunk_name('orig', x)) for x in range(1, resumableTotalChunks+1)]
    upload_complete = all([os.path.exists(p) for p in chunk_paths])

    # combine all the chunks to create the final file
    if upload_complete:
        target_file_name = os.path.join(app.config['MOVIE_PATH'], f'{video_id}_orig')
        rm_f(target_file_name)
        with open(target_file_name, "ab") as target_file:
            for p in chunk_paths:
                stored_chunk_file_name = p
                stored_chunk_file = open(stored_chunk_file_name, 'rb')
                target_file.write(stored_chunk_file.read())
                stored_chunk_file.close()
                os.unlink(stored_chunk_file_name)
        target_file.close()
        os.rmdir(temp_dir)
        app.logger.debug('File saved to: %s', target_file_name)

        cmd = f'ffprobe -v quiet -show_streams -show_format -print_format json {target_file_name}'
        output = os.popen(cmd).read()
        output = json.loads(output)
        print(output)

        if output == {}:
            print("Not a video file")
            os.unlink(target_file_name)
            return make_response(jsonify({"message": "File is not a video file"}), 400)

        vcodec = ""
        for stream in output['streams']:
            if stream['codec_type'] == 'video':
                vcodec = stream['codec_name']

        if vcodec == "":
            os.unlink(target_file_name)
            return make_response(jsonify({"message": "File is not a video file"}), 400)

        tasks.transcode.delay(target_file_name, output, video_id)

    return 'OK'

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


import shutil
import os

from flask import request, redirect, session
from flask import current_app as app
from flask_restful import Resource, marshal_with, reqparse, fields, marshal, abort
from pathlib import Path

from watchtogether.api import flask_api
from watchtogether.util import rm_f, is_video_file, get_video_title
from watchtogether.config import settings
from watchtogether.auth import ownerid
from watchtogether.database import models, db_session
from watchtogether import tasks

class VideoFileUrl(fields.Raw):
    def output(self, key, obj):
        return flask_api.url_for(VideoFile, id=obj.id, _external=True)

def get_chunk_name(uploaded_filename, chunk_number):
    return uploaded_filename + '_part_%03d' % chunk_number

def is_hole(fh, offset):
    return os.lseek(fh, offset, os.SEEK_HOLE) == offset

def target_name(video_id):
    return Path(app.config['MOVIE_PATH']) / f'{video_id}_orig'

def update_video_metadata(video, filename):
    title = get_video_title(filename)
    if title:
        video.title = title
    db_session.commit()

class VideoFile(Resource):
    def get(self, id):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=id).one_or_none()

        if not video:
            return {'message': 'Video not found'}, 403

        resumableTotalChunks = request.args.get('resumableTotalChunks', type=int)
        resumableChunkNumber = request.args.get('resumableChunkNumber', default=1, type=int)
        resumableIdentifier = request.args.get('resumableIdentifier', default='error', type=str)
        resumableFilename = request.args.get('resumableFilename', default='error', type=str)
        resumableChunkSize = request.args.get('resumableChunkSize', default=0, type=int)

        target_file_name = target_name(video.id)

        if not resumableIdentifier or not resumableChunkNumber or not resumableChunkSize:
            return {'message': 'Parameter error'}, 500

        if video.upload_identifier != resumableIdentifier:
            return {'message': 'Unknown uploader session'}, 404

        if video.orig_file_name != resumableFilename:
            return {'message': 'Different filename'}, 404

        if not target_file_name.exists():
            return {'message': 'Chunk not found'}, 404

        with open(target_file_name, "rb") as target_file:
            offset = (resumableChunkNumber - 1) * resumableChunkSize
            print(f'checking chunk: {offset}: {resumableChunkNumber}')
            fh = target_file.fileno()
            if not is_hole(fh, offset):
                return 'OK'

        return {'message': 'Chunk not found'}, 404

    def post(self, id):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=id).one_or_none()

        if not video:
            return {'message': 'Video not found'}, 403

        resumableTotalChunks = request.form.get('resumableTotalChunks', type=int)
        resumableChunkNumber = request.form.get('resumableChunkNumber', default=1, type=int)
        resumableIdentifier = request.form.get('resumableIdentifier', default='error', type=str)
        resumableFilename = request.form.get('resumableFilename', default='error', type=str)
        resumableTotalSize = request.form.get('resumableTotalSize', default=0, type=int)
        resumableChunkSize = request.form.get('resumableChunkSize', default=0, type=int)

        if not resumableIdentifier or not resumableChunkNumber or not resumableTotalSize or not resumableChunkSize:
            return {'message': 'Parameter error'}, 500

        target_file_name = target_name(video.id)
        chunk_data = request.files['file']

        if video.status in ['file-waiting', 'file-uploaded', 'ready', 'error']:
            video.status = 'file-uploading'
            video.upload_identifier = resumableIdentifier
            video.orig_file_name = resumableFilename
            video.orig_file = target_file_name.name
            db_session.commit()
                
        if video.upload_identifier != resumableIdentifier:
            return {'message': 'Different upload already in progress'}, 409

        try:
            if target_file_name.stat().st_size != resumableTotalSize or video.orig_file_name != resumableFilename:
                rm_f(target_file_name)
        except FileNotFoundError:
            pass

        if not target_file_name.exists():
            target_file = open(target_file_name, "wb")
            target_file.truncate(resumableTotalSize)
            target_file.close()

        upload_complete = False

        with open(target_file_name, "r+b") as target_file:
            offset = (resumableChunkNumber - 1) * resumableChunkSize
            target_file.seek(offset, os.SEEK_SET)
            target_file.write(chunk_data.read())

            fh = target_file.fileno()

            if os.lseek(fh, 0, os.SEEK_HOLE) == resumableTotalSize:
                upload_complete = True

            os.fsync(fh)
            print(f'Saved chunk: {offset}: {resumableChunkNumber}')

            last_chunk_offset = resumableTotalChunks * resumableChunkSize
            if (not is_hole(fh, resumableChunkSize - 1) and resumableChunkNumber == resumableTotalChunks) or (not is_hole(fh, resumableTotalSize - 1) and resumableChunkNumber == 1):
                update_video_metadata(video, target_file_name)

        if upload_complete:
            if not is_video_file(target_file_name):
                video.status = 'error'
                video.status_message = 'File uploaded was not a video file. Please use a different file.'
                db_session.commit()
                return {'message': video.status_message}, 501

            update_video_metadata(video, target_file_name)

            video.status = 'file-uploaded'
            video.encoding_progress = 0
            db_session.commit()

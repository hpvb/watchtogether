import shutil
import os

from flask import request, redirect, session, abort
from flask import current_app as app
from flask_restful import Resource, marshal_with, reqparse, fields, marshal

from watchtogether.api import flask_api
from watchtogether.util import rm_f
from watchtogether.config import settings
from watchtogether.auth import ownerid
from watchtogether.database import models, db_session
from watchtogether import tasks

from . import ValidValueParser
from.video_file import VideoFile, VideoFileUrl

video_fields = {
    'url': fields.Url('video', absolute=True),
    'file_url': VideoFileUrl(),
    'id': fields.String,
    'title': fields.String,
    'width': fields.Integer,
    'height': fields.Integer,
    'duration': fields.Float,
    'encoding_progress': fields.Integer,
    'encoding_speed': fields.Float,
    'status': fields.String,
    'tune': fields.String,
    'default_subtitles': fields.Boolean,
    'orig_file_name': fields.String
}

def VideoTuneParser(value):
    valid = ['film', 'animation', 'grain']
    return ValidValueParser('Tune', value, valid)

def VideoStateParser(value):
    valid = ['file-waiting', 'start-encoding']
    return ValidValueParser('State', value, valid)

new_video_parser = reqparse.RequestParser()
new_video_parser.add_argument('title', nullable=False, required=True)

video_parser = reqparse.RequestParser()
video_parser.add_argument('title', nullable=False, required=False)
video_parser.add_argument('tune', type=VideoTuneParser, nullable=False, required=False)
video_parser.add_argument('status', type=VideoStateParser, nullable=False, required=False)

class Video(Resource):
    @marshal_with(video_fields)
    def get(self, id):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=id).one_or_none()

        if not video:
            abort(404, 'Video not found')

        return video

    @marshal_with(video_fields)
    def post(self, id):
        args = video_parser.parse_args()

        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=id).one_or_none()

        if not video:
            abort(404, 'Video not found')

        if args.get('title'):
            if not video.status in ['start-encoding', 'encoding']:
                video.title = args.get('title')
            else:
                abort(409, 'Cannot change video title while encoding')

        if args.get('tune'):
            if not video.status in ['start-encoding', 'encoding']:
                video.tune = args.get('tune')
            else:
                abort(409, 'Cannot change video tuning while encoding')

        if args.get('status'):
            status = args.get('status')
            if status == 'file-waiting':
                if not video.status in ['encoding', 'start-encoding']:
                    video.status = status
                    video.upload_identifier = None
                else:
                    abort(409, 'Cannot upload new file while encoding')

            if status == 'start-encoding':
                if video.status in ['file-uploaded', 'ready']:
                    video.status = status
                    video.encoding_progress = 0
                    video.status_error =""
                    tasks.transcode.delay(video.id)
                else:
                    abort(409, 'Cannot start encoding while video is in this state')

        db_session.commit()

        return video

    def delete(self, id):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=id).one_or_none()

        if not video:
            abort(404, 'Video not found')

        if video.status in ['encoding', 'start-encoding']:
            abort(409, 'Cannot delete while encoding')

        try:
            if (video.playlist):
                rm_f(video.playlist)

            if (video.orig_file):
                rm_f(os.path.join(app.config['MOVIE_PATH'], video.orig_file))

            if app.config['STORAGE_BACKEND'] == 'S3':
                tasks.s3_delete.delay(video.id)
            else:
                viddir = f"{app.config['MOVIE_PATH']}/{video.id}"
                shutil.rmtree(viddir, ignore_errors = True)
        except:
            abort(500)

        db_session.delete(video)
        db_session.commit()

        return {'message': 'Video deleted'}, 204

class VideoList(Resource):
    @marshal_with(video_fields)
    def get(self):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        res = db_session.query(models.Video).filter_by(owner=owner_id).all()
        return res

    @marshal_with(video_fields)
    def put(self):
        args = new_video_parser.parse_args()

        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        if not owner_id:
            abort(403)

        video = models.Video(title=args['title'], owner=owner_id)
        db_session.add(video)
        db_session.commit()

        return video
        

import shutil
import os

from flask import request, redirect, session, abort, url_for
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
from.subtitle import SubtitleList, subtitle_fields

class SubtitlesListUrl(fields.Raw):
    def output(self, key, obj):
        return flask_api.url_for(SubtitleList, video_id=obj.id, _external=True)

class VideoWatchUrl(fields.Raw):
    def output(self, key, obj):
        return url_for('main.watch', video_id=obj.id, _external=True)

class VideoUrl(fields.Raw):
    def output(self, key, obj):
        return flask_api.url_for(Video, video_id=obj.id, _external=True)

def VideoTuneParser(value):
    valid = ['film', 'animation', 'grain']
    return ValidValueParser('Tune', value, valid)

def VideoStateParser(value):
    valid = ['file-waiting', 'start-encoding']
    return ValidValueParser('State', value, valid)

video_fields = {
    'url': VideoUrl,
    'file_url': VideoFileUrl,
    'watch_url': VideoWatchUrl,
    'subtitles_url': SubtitlesListUrl,
    'id': fields.String,
    'title': fields.String,
    'width': fields.Integer,
    'height': fields.Integer,
    'duration': fields.Float,
    'encoding_progress': fields.Float,
    'encoding_speed': fields.Float,
    'status': fields.String,
    'status_message': fields.String,
    'tune': fields.String,
    'default_subtitles': fields.Boolean,
    'orig_file_name': fields.String,
}

new_video_parser = reqparse.RequestParser()
new_video_parser.add_argument('title', nullable=False, required=True)

video_parser = reqparse.RequestParser()
video_parser.add_argument('title', nullable=False, required=False)
video_parser.add_argument('tune', type=VideoTuneParser, nullable=False, required=False)
video_parser.add_argument('status', type=VideoStateParser, nullable=False, required=False)

class Video(Resource):
    @marshal_with(video_fields)
    def get(self, video_id):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=video_id).one_or_none()

        if not video:
            abort(404, 'Video not found')

        return video

    @marshal_with(video_fields)
    def post(self, video_id):
        args = video_parser.parse_args()

        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=video_id).one_or_none()

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
                if video.status in ['file-uploaded', 'ready', 'error']:
                    video.status = status
                    video.encoding_progress = 0
                    video.status_error =""
                    video.celery_taskid = tasks.transcode.delay(video.id)
                else:
                    abort(409, 'Cannot start encoding while video is in this state')

        db_session.commit()

        return video

    def delete(self, video_id):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=video_id).one_or_none()

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
        

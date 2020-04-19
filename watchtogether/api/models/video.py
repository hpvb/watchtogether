import shutil
import os

from flask import request, redirect, session
from flask import current_app as app
from flask_restful import Resource, marshal_with, reqparse, fields, marshal, abort

from watchtogether.api import flask_api
from watchtogether.util import rm_f
from watchtogether.config import settings
from watchtogether.auth import ownerid
from watchtogether.database import models, db_session
from watchtogether import tasks

video_fields = {
    'url': fields.Url('video', absolute=True),
    'id': fields.String,
    'title': fields.String,
    'width': fields.Integer,
    'height': fields.Integer,
    'duration': fields.Float,
    'encoding_progress': fields.Integer,
    'encoding_speed': fields.Float,
    'encoding_status': fields.String,
    'tune': fields.String,
    'default_subtitles': fields.Boolean,
}

video_parser = reqparse.RequestParser()
video_parser.add_argument('title', nullable=False, required=True)

class Video(Resource):
    @marshal_with(video_fields)
    def get(self, id):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=id).one_or_none()

        if not video:
            abort(404)

        return video

    def delete(self, id):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=id).one_or_none()

        if not video:
            abort(404)

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

        return "Video deleted", 204

class VideoList(Resource):
    @marshal_with(video_fields)
    def get(self):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        res = db_session.query(models.Video).filter_by(owner=owner_id).all()
        return res

    @marshal_with(video_fields)
    def put(self):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        if not owner_id:
            abort(403)

        args = video_parser.parse_args()
        video = models.Video(title=args['title'], owner=owner_id)
        db_session.add(video)
        db_session.commit()

        return video
        


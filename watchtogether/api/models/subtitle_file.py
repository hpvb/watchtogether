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

class SubtitleFileUrl(fields.Raw):
    def output(self, key, obj):
        return flask_api.url_for(SubtitleFile, video_id=obj.video_id, subtitle_id=int(obj.id), _external=True)

class SubtitleFile(Resource):
    def post(self, video_id, subtitle_id):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=video_id).one_or_none()
        subtitle = db_session.query(models.Subtitle).filter_by(id=subtitle_id, video_id=video_id).one_or_none()

        if not video:
            abort(404, 'Video not found')

        if not subtitle:
            abort(404, 'Subtitle not found')

        file = request.files['file']
        filename = f'{video.id}_sub_{subtitle.id}_orig'
        file.save(os.path.join(app.config['MOVIE_PATH'], filename))
        subtitle.orig_file_name = filename
        db_session.commit()

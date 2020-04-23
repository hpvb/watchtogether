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
from.subtitle_file import SubtitleFile, SubtitleFileUrl

class SubtitleUrl(fields.Raw):
    def output(self, key, obj):
        return flask_api.url_for(Subtitle, video_id=obj.video_id, subtitle_id=int(obj.id), _external=True)

def LanguageParser(value):
    value = value.strip()

    if len(value) > 3:
        raise ValueError('Language codes can only be 3 characters long. Like "eng" or "jpn".')

    return value

subtitle_fields = {
    'url': SubtitleUrl,
    'file_url': SubtitleFileUrl,
    'title': fields.String,
    'language': fields.String,
}

new_subtitle_parser = reqparse.RequestParser()
new_subtitle_parser.add_argument('title', nullable=False, required=True)
new_subtitle_parser.add_argument('language', type=LanguageParser, nullable=False, required=True)

class Subtitle(Resource):
    @marshal_with(subtitle_fields)
    def get(self, video_id, subtitle_id):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=video_id).one_or_none()
        subtitle = db_session.query(models.Subtitle).filter_by(id=subtitle_id, video_id=video_id).one_or_none()

        if not video:
            abort(404, 'Video not found')

        if not subtitle:
            abort(404, 'Subtitle not found')

        return subtitle

    @marshal_with(subtitle_fields)
    def post(self, video_id, subtitle_id):
        args = new_subtitle_parser.parse_args()

        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=video_id).one_or_none()
        subtitle = db_session.query(models.Subtitle).filter_by(id=subtitle_id, video_id=video_id).one_or_none()

        if not video:
            abort(404, 'Video not found')

        if not subtitle:
            abort(404, 'Subtitle not found')

        subtitle.title = args['title']
        subtitle.language = args['language']
        db_session.commit()

        return subtitle

class SubtitleList(Resource):
    @marshal_with(subtitle_fields)
    def get(self, video_id):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=video_id).one_or_none()
        return video.subtitles

    @marshal_with(subtitle_fields)
    def put(self, video_id):
        args = new_subtitle_parser.parse_args()

        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        if not owner_id:
            abort(403)

        video = db_session.query(models.Video).filter_by(owner=owner_id, id=video_id).one_or_none()
        if not video:
            abort(404, 'Video not found')

        subtitle = models.Subtitle(
            video_id = video.id,
            language = args['language'],
            title = args['title'],
        )

        db_session.add(subtitle)
        db_session.commit()

        return subtitle

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

class VideoFileUrl(fields.Raw):
    def output(self, key, obj):
        return flask_api.url_for(VideoFile, id=obj.id, _external=True)

def get_chunk_name(uploaded_filename, chunk_number):
    return uploaded_filename + '_part_%03d' % chunk_number

class VideoFile(Resource):
    def get(self, id):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=id).one_or_none()

        if not video:
            return {'message': 'Video not found'}, 403

        resumableIdentfier = request.args.get('resumableIdentifier', type=str)
        resumableChunkNumber = request.args.get('resumableChunkNumber', type=int)

        if not resumableIdentfier or not resumableChunkNumber:
            return {'message': 'Parameter error'}, 500

        # chunk path based on the parameters
        temp_dir = os.path.join(app.config['MOVIE_PATH'], video.id, 'tmp', resumableIdentfier)
        chunk_name = get_chunk_name('orig', resumableChunkNumber)
        chunk_file = os.path.join(temp_dir, chunk_name)
        print(f'Getting chunk: {chunk_file}')

        if os.path.isfile(chunk_file):
            # Let resumable.js know this chunk already exists
            return 'OK'
        else:
            # Let resumable.js know this chunk does not exists and needs to be uploaded
            return {'message': 'Not found'}, 404

    def post(self, id):
        owner_id = request.cookies.get(app.config['COOKIE_OWNER_ID'])
        video = db_session.query(models.Video).filter_by(owner=owner_id, id=id).one_or_none()

        if not video:
            return {'message': 'Video not found'}, 403

        resumableTotalChunks = request.form.get('resumableTotalChunks', type=int)
        resumableChunkNumber = request.form.get('resumableChunkNumber', default=1, type=int)
        resumableIdentfier = request.form.get('resumableIdentifier', default='error', type=str)

        if not resumableIdentfier or not resumableChunkNumber:
            return {'message': 'Parameter error'}, 500

        if video.status == 'file-waiting' and resumableChunkNumber == 1:
            video.status = 'file-uploading'
            video.upload_identifier = resumableIdentfier
            db_session.commit()

        if video.status == 'file-uploading':
            if video.upload_identifier != resumableIdentfier:
                return {'message': 'Different upload already in progress'}, 409

        # get the chunk data
        chunk_data = request.files['file']

        # make our temp directory
        temp_dir = os.path.join(app.config['MOVIE_PATH'], video.id, 'tmp', resumableIdentfier)
        if not os.path.isdir(temp_dir):
            os.makedirs(temp_dir)

        # save the chunk data
        chunk_name = get_chunk_name('orig', resumableChunkNumber)
        chunk_file = os.path.join(temp_dir, chunk_name)
        chunk_data.save(chunk_file)
        print(f'Saved chunk: {chunk_file}')

        # check if the upload is complete
        chunk_paths = [os.path.join(temp_dir, get_chunk_name('orig', x)) for x in range(1, resumableTotalChunks+1)]
        upload_complete = all([os.path.exists(p) for p in chunk_paths])

        # combine all the chunks to create the final file
        if upload_complete:
            target_file_name = os.path.join(app.config['MOVIE_PATH'], f'{video.id}_orig')
            rm_f(target_file_name)
            with open(target_file_name, 'ab') as target_file:
                for p in chunk_paths:
                    stored_chunk_file_name = p
                    stored_chunk_file = open(stored_chunk_file_name, 'rb')
                    target_file.write(stored_chunk_file.read())
                    stored_chunk_file.close()
                    os.unlink(stored_chunk_file_name)
            target_file.close()
            os.rmdir(temp_dir)

            print(f'Saved file as: {target_file_name}')
            video.status = 'file-uploaded'
            video.encoding_progress = 0
            video.orig_file = target_file_name
            db_session.commit()

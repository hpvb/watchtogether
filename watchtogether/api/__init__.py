import flask_restful
flask_api = flask_restful.Api()

from watchtogether.api.models import *

flask_api.add_resource(VideoList, '/api/videos/')
flask_api.add_resource(Video, '/api/videos/<id>')
flask_api.add_resource(VideoFile, '/api/videos/<id>/video_file')


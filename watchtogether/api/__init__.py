import flask_restful
flask_api = flask_restful.Api()

from watchtogether.api.models import *

flask_api.add_resource(VideoList, '/api/videos/')
flask_api.add_resource(Video, '/api/videos/<video_id>')
flask_api.add_resource(VideoFile, '/api/videos/<video_id>/file')
flask_api.add_resource(SubtitleList, '/api/videos/<video_id>/subtitles')
flask_api.add_resource(Subtitle, '/api/videos/<video_id>/subtitles/<subtitle_id>')
flask_api.add_resource(SubtitleFile, '/api/videos/<video_id>/subtitles/<subtitle_id>/file')


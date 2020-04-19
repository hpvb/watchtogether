import flask
import string
from watchtogether.util import random_string
from watchtogether.config import settings

def ownerid(f):
    def decorated_function(*args, **kwargs):
        owner_id = None
        if settings.COOKIE_OWNER_ID in flask.request.cookies.keys():
            owner_id = flask.request.cookies[settings.COOKIE_OWNER_ID]
        else:
            letters = string.ascii_lowercase
            owner_id = random_string(15)

        f.__globals__['owner_id'] = owner_id
        response = f(*args, **kwargs)
        if not hasattr(response, 'set_cookie'):
            response = flask.make_response(response)
        response.set_cookie(settings.COOKIE_OWNER_ID, value=owner_id, max_age=60*60*24*365*10)
        return response

    decorated_function.__name__ = f.__name__
    return decorated_function


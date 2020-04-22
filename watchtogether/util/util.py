import os
import random
import string
import json
import pprint

pp = pprint.PrettyPrinter(indent=4)

def random_string(length):
    letters = string.ascii_lowercase
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def rm_f(filename):
    try:
        os.unlink(filename)
    except FileNotFoundError:
        pass
    except TypeError:
        pass

def ffprobe(filename):
    cmd = f'ffprobe -v quiet -show_streams -show_format -print_format json {filename}'
    streaminfo = os.popen(cmd).read()
    return json.loads(streaminfo)

def is_video_file(filename):
    streaminfo = ffprobe(filename)
    try:
        if 'probe_score' in streaminfo['format']:
            if streaminfo['format']['probe_score'] < 25:
                raise Exception
        if float(streaminfo['format']['duration']) < 10:
            raise Exception
    except Exception:
        return False

    return True

def get_video_title(filename):
    streaminfo = ffprobe(filename)
    try:
        return streaminfo['format']['tags']['title']
    except KeyError:
        return None

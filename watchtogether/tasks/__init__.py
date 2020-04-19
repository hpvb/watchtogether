#!/usr/bin/env python3

import os
import glob
import shutil
import socket
import threading
import tempfile
import subprocess

import numpy 
import boto3
import boto3.session
from botocore.exceptions import NoCredentialsError

from celery import Celery
import billiard as multiprocessing

from watchtogether.database import models, db_session, init_engine
from watchtogether.config import settings
from watchtogether.util import rm_f

celery = Celery(__name__, broker=settings.CELERY_BROKER_URL)
celery.conf.update(settings.as_dict())
init_engine(settings.SQLALCHEMY_DATABASE_URI)

def s3_upload(files):
    params = {
        'aws_access_key_id': celery.conf.get('S3_ACCESS_KEY'),
        'aws_secret_access_key': celery.conf.get('S3_SECRET_KEY'),
    }

    if celery.conf.get('S3_ENDPOINT_URL'):
        params['endpoint_url'] = celery.conf.get('S3_ENDPOINT_URL')

    if celery.conf.get('S3_REGION'):
        params['region_name'] = celery.conf.get('S3_REGION')

    session = boto3.session.Session()
    s3 = session.resource('s3', **params)
    bucket = s3.Bucket(celery.conf.get('S3_BUCKET'))

    for f in files:
        tries = 0
        while tries < 10:
            try:
                bucket.upload_file(f, "/".join(f.split("/")[-2:]), ExtraArgs={'ACL': 'public-read'})
                break
            except:
                tries = tries + 1

@celery.task
def s3_delete(video_id):
    params = {
        'aws_access_key_id': celery.conf.get('S3_ACCESS_KEY'),
        'aws_secret_access_key': celery.conf.get('S3_SECRET_KEY'),
    }

    if celery.conf.get('S3_ENDPOINT_URL'):
        params['endpoint_url'] = celery.conf.get('S3_ENDPOINT_URL')

    if celery.conf.get('S3_REGION'):
        params['region_name'] = celery.conf.get('S3_REGION')

    session = boto3.session.Session()
    s3 = session.resource('s3', **params)
    bucket = s3.Bucket(celery.conf.get('S3_BUCKET'))
    bucket.objects.filter(Prefix=f"{video_id}/").delete()

def run_ffmpeg(command, logfile):
    print(f'Executing: {" ".join(command)}')
    with open(logfile, 'w') as lf:
        output = subprocess.run(command, stderr=lf)

@celery.task
def transcode(tmpfile, streaminfo, video_id):
    status = 'error'
    output = ""

    outdir = f"{celery.conf.get('MOVIE_PATH')}/{video_id}"
    shutil.rmtree(outdir, ignore_errors = True)
    os.mkdir(outdir)

    master_playlist = f"{outdir}/playlist.mpd"
    rm_f(master_playlist)

    vwidth = 0
    vheight = 0
    duration = 0
    acodec = ""
    vcodec = ""
    framerate = 24
    chunk_size = 4

    video_streamidx = -1
    audio_streamidx = -1
    has_audio = False

    video = db_session.query(models.Video).filter_by(id=video_id).one_or_none()

    duration = float(streaminfo['format']['duration'])
    for stream in streaminfo['streams']:
        if stream['codec_type'] == 'video':
            vcodec = stream['codec_name']
            vwidth = stream['width']
            vheight = stream['height']
            framerate = stream['r_frame_rate']
            video_streamidx = stream['index']
        if stream['codec_type'] == 'audio':
            has_audio = True
            if audio_streamidx == -1 and stream['tags']['language'] == 'und':
                audio_streamidx = stream['index']
                audio_codec = stream['codec_name']
            if stream['tags']['language'] == 'eng':
                audio_streamidx = stream['index']
                audio_codec = stream['codec_name']

    if video_streamidx == -1:
        video_streamidx = 0
    if audio_streamidx == -1 and has_audio:
        audio_streamidx = 1

    try:
        framerate = round(float(framerate))
    except ValueError:
        x, y = framerate.split("/")
        framerate = round(int(x) / int(y))

    dash_size = 4
    keyint = framerate
    if vwidth > 1920:
        vheight = int(vheight / (vwidth / 1920))
        vwidth = 1920
    
    audio_formats = []
    if has_audio:
        audio_formats = [
            {'rate': '64k', 'channels': '1'},
            {'rate': '128k', 'channels': '2'},
            {'rate': '196k', 'channels': '2'}
        ]

    video_profiles = [
        {'profile': 'main', 'preset': 'veryslow', 'crf': '22', 'maxrate': '600k', 'bufsize': '800k', 'width': 480},
        {'profile': 'main', 'preset': 'slow', 'crf': '22', 'maxrate': '900k', 'bufsize': '1200k', 'width': 640},
        {'profile': 'high', 'preset': 'slow', 'crf': '22', 'maxrate': '1200k', 'bufsize': '1500k', 'width': 960},
        {'profile': 'high', 'preset': 'slow', 'crf': '21', 'maxrate': '2000k', 'bufsize': '4000k', 'width': 1280},
        {'profile': 'high', 'preset': 'slow', 'crf': '21', 'maxrate': '4500k', 'bufsize': '8000k', 'width': 1920},
    ]

    video_formats = [
        {'profile': 'baseline', 'preset': 'veryslow', 'crf': '22', 'maxrate': '200k', 'bufsize': '300k', 'width': 320},
        {'profile': 'baseline', 'preset': 'veryslow', 'crf': '22', 'maxrate': '400k', 'bufsize': '500k', 'width': 320}
    ]

    sizes = [1, 1.5, 2, 3]
    for size in sizes:
        this_width = int(vwidth / size) + (int(vwidth / size) % 2)
        if this_width < video_profiles[0]['width']:
            next

        this_profile = None
        for idx in range(len(video_profiles)):
            if this_width == video_profiles[idx]['width']:
                this_profile = video_profiles[idx].copy()
                break

            if this_width > video_profiles[idx]['width'] and this_width < video_profiles[idx + 1]['width']:
                this_profile = video_profiles[idx + 1].copy()
                this_profile['width'] = this_width
                break

        if this_profile:
            video_formats.append(this_profile)

    print(video_formats)

    tmpdir = tempfile.mkdtemp()
    socketfile = os.path.join(tmpdir, 'progress')
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(socketfile)
    sock.listen(1)

    transcode_command = ['ffmpeg', '-y', '-nostdin', '-i', f'{tmpfile}', '-progress', f'unix://{socketfile}', '-loglevel', '24']
    dash_command = ['MP4Box', '-dash', f'{dash_size * 1000}', '-rap', '-frag-rap', '-min-buffer', '16000', '-profile', 'dashavc264:onDemand', '-mpd-title', video.title ,'-out', master_playlist]
    tmpfiles = []
    for num, f in enumerate(video_formats):
        stream = num
        filename = f'{outdir}/video_{f["width"]}_{f["maxrate"]}.mp4'
        transcode_command.extend(['-map', f'0:{video_streamidx}', f'-c:v', 'libx264', '-x264-params', f'no-scenecut', f'-profile:v', f['profile'], '-preset:v', f["preset"], '-tune:v', video.tune,
            '-keyint_min', f'{keyint}', '-g', f'{keyint}', '-sc_threshold', '0', '-bf', '1', '-b_strategy', '0',
            f'-crf', f['crf'], f'-maxrate', f'{f["maxrate"]}', f'-bufsize', f'{f["bufsize"]}', f'-filter', f'scale={f["width"]}:-2',
            '-map_chapters', '-1', filename])
        dash_command.append(filename)
        tmpfiles.append(filename)

    for num, f in enumerate(audio_formats):
        stream = num 
        filename = f'{outdir}/audio_{f["rate"]}.mp4'
        transcode_command.extend(['-map', f'0:{audio_streamidx}', f'-c:a', 'aac', f'-b:a', f['rate'], f'-ac', f['channels'], '-map_chapters', '-1', filename])
        dash_command.append(filename)
        tmpfiles.append(filename)

    video.encoding_status = 'encoding'
    db_session.commit()

    ffmpeg = multiprocessing.Process(target=run_ffmpeg, args=(transcode_command, f'{tmpfile}.log'))
    ffmpeg.start()
    connection, client_address = sock.accept()
    percentage = 0
    speed = 0

    try:
        while True:
            data = connection.recv(1024)
            if data:
                string = data.decode('utf-8')
                for line in string.splitlines():
                    if line.startswith('out_time_ms'):
                        progress = int(line.split('=')[1]) / 1000000
                        percentage = (progress / duration) * 100
                        percentage = min(percentage, 100)
                    if line.startswith('speed'):
                        speed = float(line.split('=')[1].strip().split('x')[0])

                video.encoding_progress = percentage
                video.encoding_speed = speed
                db_session.commit()
            else:
                break

    finally:
        ffmpeg.terminate()
        connection.close()
        shutil.rmtree(tmpdir, ignore_errors = True)

        if percentage < 100:
            video.status = 'error'
            db_session.commit()

    try:
        print("Reencoded file")
        print(f'Executing: {" ".join(dash_command)}')
        output = subprocess.check_call(dash_command, stderr=subprocess.STDOUT)
        print("DASHed file")

        status = 'ready'

    except Exception as e:
        print(output)
        print(e)

    for f in tmpfiles:
        os.unlink(f)

    if celery.conf.get('STORAGE_BACKEND') == "S3":
        print("Uploading to S3")

        nthreads = celery.conf.get('S3_UPLOAD_THREADS')
        g = glob.glob(f"{outdir}/*")
        splits = numpy.array_split(g, nthreads)
        threads = list()

        for index in range(nthreads):
            x = threading.Thread(target=s3_upload, args=(splits[index].copy(),))
            threads.append(x)
            x.start()

        for index, thread in enumerate(threads):
            thread.join()

        shutil.rmtree(outdir, ignore_errors = True)
        print("Done uploading")

    video.playlist = f'{video_id}/playlist.mpd'
    video.width = vwidth
    video.height = vheight
    video.duration = duration
    video.encoding_status = status
    db_session.commit()


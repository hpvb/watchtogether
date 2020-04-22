#!/usr/bin/env python3

import os
import glob
import json
import shutil
import socket
import hashlib
import tempfile
import threading
import subprocess

import numpy 
import boto3
import boto3.session
from botocore.exceptions import NoCredentialsError

from celery import Celery, states
from celery.exceptions import Ignore
import billiard as multiprocessing

from watchtogether.database import models, db_session, init_engine
from watchtogether.config import settings
from watchtogether.util import rm_f, ffprobe

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

class FfmpegException(Exception):
    pass

class FfmpegTranscode:
    def __init__(self, video, task, outdir):
        self.video = video
        self.task = task
        self.outdir = outdir
        self.tmpdir = tempfile.mkdtemp()
        self.socketfile = os.path.join(self.tmpdir, 'progress')
        self.orig_file = os.path.join(celery.conf.get('MOVIE_PATH'), video.orig_file)
        self.streaminfo = ffprobe(self.orig_file)
        self.has_audio = False
        self.audio_streams = []
        self.audio_streamidx = -1
        self.video_streams = []
        self.video_streamidx = -1
        self.ffmpeg_command = ['ffmpeg', '-y', '-nostdin', '-i', f'{self.orig_file}', '-progress', f'unix://{self.socketfile}', '-loglevel', '24']
        self.encoded_files = []
        self.has_work = False

        self.get_metadata()
        self.create_streams()
        self.create_command()

    def __del__(self):
        shutil.rmtree(self.tmpdir, ignore_errors = True)

    def get_metadata(self):
        try:
            for stream in self.streaminfo['streams']:
                if stream['codec_type'] == 'video':
                    vcodec = stream['codec_name']
        except:
            raise FfmpegException('Unable to parse file, not a video file?')

        if vcodec == "":
            raise FfmpegException('Uploaded file was not a video file.')

        self.duration = float(self.streaminfo['format']['duration'])
        for stream in self.streaminfo['streams']:
            if stream['codec_type'] == 'video':
                self.vcodec = stream['codec_name']
                self.vwidth = stream['width']
                self.vheight = stream['height']
                self.framerate = stream['r_frame_rate']
                self.video_streamidx = stream['index']
            if stream['codec_type'] == 'audio':
                self.has_audio = True
                if self.audio_streamidx == -1 and stream['tags']['language'] != 'eng':
                    self.audio_streamidx = stream['index']
                    self.audio_codec = stream['codec_name']
                if stream['tags']['language'] == 'eng':
                    self.audio_streamidx = stream['index']
                    self.audio_codec = stream['codec_name']

        if self.video_streamidx == -1:
            self.video_streamidx = 0
        if self.audio_streamidx == -1 and has_audio:
            self.audio_streamidx = 1

        try:
            self.framerate = round(float(self.framerate))
        except ValueError:
            x, y = self.framerate.split("/")
            self.framerate = round(int(x) / int(y))

        self.keyint = self.framerate
        if self.vwidth > 1920:
            self.vheight = int(self.vheight / (self.vwidth / 1920))
            self.vwidth = 1920

    def create_streams(self):
        if self.has_audio:
            self.audio_streams = [
                {'rate':  '64k', 'channels': '1'},
                {'rate': '128k', 'channels': '2'},
                {'rate': '196k', 'channels': '2'}
            ]

        video_profiles = [
            {'profile': 'main', 'preset': 'medium', 'crf': '22', 'maxrate': '900k', 'bufsize': '1200k', 'width': 640},
            {'profile': 'high', 'preset': 'medium', 'crf': '22', 'maxrate': '1200k', 'bufsize': '1500k', 'width': 960},
            {'profile': 'high', 'preset': 'medium', 'crf': '21', 'maxrate': '2000k', 'bufsize': '4000k', 'width': 1280},
            {'profile': 'high', 'preset': 'medium', 'crf': '21', 'maxrate': '4500k', 'bufsize': '8000k', 'width': 1920},
        ]

        self.video_streams = [
            {'profile': 'baseline', 'preset': 'slow', 'crf': '22', 'maxrate': '200k', 'bufsize': '300k', 'width': 320},
            {'profile': 'baseline', 'preset': 'slow', 'crf': '22', 'maxrate': '400k', 'bufsize': '500k', 'width': 480}
        ]

        sizes = [1, 1.5, 2, 3]
        for size in sizes:
            this_width = int(self.vwidth / size) + (int(self.vwidth / size) % 2)
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
                self.video_streams.append(this_profile)

    def create_stream(self, command, filename, stream_type):
        outfile = f'{self.outdir}/{filename}'
        command_hash = hashlib.sha256(str(command).encode('utf-8')).hexdigest()

        encoded_file = db_session.query(models.EncodedFile).filter_by(
            video_id = self.video.id,
            encoded_file_name = filename,
            encoding_hash = command_hash
        ).one_or_none()

        if not encoded_file or not os.path.isfile(outfile):
            encoded_file = models.EncodedFile(
                video_id = self.video.id,
                encoded_file_name = filename,
                encoding_hash = command_hash,
                track_type = stream_type
            )

            self.encoded_files.append(encoded_file)
            self.ffmpeg_command.extend(command)
            self.ffmpeg_command.append(outfile)
            self.has_work = True

    def create_command(self):
        for num, f in enumerate(self.video_streams):
            filename = f'video_{f["width"]}_{f["maxrate"]}.mp4'
            command = ['-map', f'0:{self.video_streamidx}', '-an', '-sn', '-dn', f'-c:v', 'libx264', '-x264-params', f'no-scenecut', f'-profile:v', f['profile'], '-preset:v', f["preset"], '-tune:v', self.video.tune,
                '-keyint_min', f'{self.keyint}', '-g', f'{self.keyint}', '-sc_threshold', '0', '-bf', '1', '-b_strategy', '0',
                f'-crf', f['crf'], f'-maxrate', f'{f["maxrate"]}', f'-bufsize', f'{f["bufsize"]}', f'-filter', f'scale={f["width"]}:-2',
                '-map_chapters', '-1']

            self.create_stream(command, filename, 'video')

        for num, f in enumerate(self.audio_streams):
            filename = f'audio_{f["rate"]}.mp4'
            command = ['-map', f'0:{self.audio_streamidx}', '-vn', '-sn', '-dn', f'-c:a', 'aac', f'-b:a', f['rate'], f'-ac', f['channels'], '-map_chapters', '-1']

            self.create_stream(command, filename, 'audio')

    def run_ffmpeg(self, command, logfile):
        print(f'Executing: {" ".join(command)}')
        with open(logfile, 'w') as lf:
            output = subprocess.run(command, stderr=lf)

    def ffmpeg_progress(self, logfile):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(15)
        sock.bind(self.socketfile)
        sock.listen(1)

        ffmpeg = multiprocessing.Process(target=self.run_ffmpeg, args=(self.ffmpeg_command, logfile))
        ffmpeg.start()
        percentage = 0
        speed = 0
        ffmpeg_clean_end = False

        try:
            connection, client_address = sock.accept()
            while True:
                data = connection.recv(1024)
                if data:
                    string = data.decode('utf-8')
                    for line in string.splitlines():
                        if line.startswith('out_time_ms'):
                            progress = int(line.split('=')[1]) / 1000000
                            percentage = (progress / self.duration) * 100
                            percentage = min(percentage, 100)
                        if line.startswith('speed'):
                            speed = float(line.split('=')[1].strip().split('x')[0])
                        if line.startswith('progress'):
                            if line.split('=')[1].strip() == 'end':
                                ffmpeg_clean_end = True

                    self.video.encoding_progress = percentage
                    self.video.encoding_speed = speed
                    db_session.commit()
                else:
                    break
        except socket.timeout:
            pass

        finally:
            ffmpeg.terminate()
            connection.close()

            if percentage < 100:
                status = ""
                if ffmpeg_clean_end:
                    status = "Encoding failed"
                else:
                    status = "Encoder crash"
                    
                raise FfmpegException(status)

    def run(self):
        self.video.status = 'encoding'
        self.video.width = self.vwidth
        self.video.height = self.vheight
        self.video.duration = self.duration
        db_session.commit()

        if self.has_work:
            self.ffmpeg_progress(f'{self.orig_file}.log')
            for encoded_file in self.encoded_files:
                db_session.add(encoded_file)
            db_session.commit()

@celery.task(bind=True)
def transcode(self, video_id):
    video = db_session.query(models.Video).filter_by(id=video_id).one_or_none()
    video.status = 'encoding'
    db_session.commit()

    outdir = f"{celery.conf.get('MOVIE_PATH')}/{video.id}"
    try:
        os.mkdir(outdir)
    except FileExistsError:
        pass

    try:
        ffmpeg = FfmpegTranscode(video, self, outdir)
        ffmpeg.run()
        transcode_video(video, self)
    except FfmpegException as e:
        video.status = 'error'
        video.status_message = str(e)
        db_session.commit()

        self.update_state(
            state = states.FAILURE,
            meta = str(e)
        )

        raise Ignore()

def transcode_video(video, task):
    status = 'error'
    output = ""

    outdir = f"{celery.conf.get('MOVIE_PATH')}/{video.id}"
    try:
        os.mkdir(outdir)
    except FileExistsError:
        pass

    master_playlist = f"{outdir}/playlist.mpd"
    rm_f(master_playlist)

    dash_size = 4
    dash_command = ['MP4Box', '-dash', f'{dash_size * 1000}', '-rap', '-frag-rap', '-min-buffer', '16000', '-profile', 'dashavc264:onDemand', '-mpd-title', video.title ,'-out', master_playlist]
    try:
        print("Reencoded file")
        for encoded_file in video.encoded_files:
            dash_command.append(f'{outdir}/{encoded_file.encoded_file_name}')

        print(f'Executing: {" ".join(dash_command)}')
        output = subprocess.check_call(dash_command, stderr=subprocess.STDOUT)
        print("DASHed file")

        status = 'ready'

    except Exception as e:
        print(output)
        print(e)
        video.status = 'error'
        video.status_message = 'MP4Box failed'
        db_session.commit()

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

    video.playlist = f'{video.id}/playlist.mpd'
    video.status = status
    db_session.commit()


FROM fedora:31
  
LABEL maintainer="Hein-Pieter van Braam-Stewart <hp@tmm.cx>"

RUN dnf -y install https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-31.noarch.rpm && \
    dnf -y install ffmpeg python3-pip python3-alembic python3-mysql python3-flask python3-flask-sqlalchemy python3-flask-restful python3-gunicorn python3-eventlet python3-celery python3-redis python3-numpy python3-boto3 gpac && \
    pip3 install flask-socketio && \
    dnf clean all

COPY watchtogether /root/watchtogether
COPY entrypoint.sh /root

VOLUME /root/watchtogether/static/movies

WORKDIR /root
ENTRYPOINT ["/root/entrypoint.sh"]
CMD [""]

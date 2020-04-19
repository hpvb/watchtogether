Watch Together
--------------

A simple Python application to watch movies together with your friends. See `config/settings.py` for knobs. See Dockerfile for dependencies on F31.

Example usage of the container using podman:
```
containers="watchtogether-app watchtogether-worker watchtogether-celery watchtogether-redis"
for container in $containers; do
	podman rm --force $container
done

podman pod rm watchtogether

podman pod create --name watchtogether -p 127.0.0.1:8087:5000 -p 127.0.0.1:8088:5001
podman run -dt --pod watchtogether --name watchtogether-app --env-file /srv/watchtogether/app-env -v /srv/watchtogether/movies:/root/watchtogether/static/movies watchtogether:latest app
podman run -dt --pod watchtogether --name watchtogether-worker --env-file /srv/watchtogether/app-env -v /srv/watchtogether/movies:/root/watchtogether/static/movies watchtogether:latest workers
podman run -dt --pod watchtogether --name watchtogether-celery --env-file /srv/watchtogether/app-env --cpu-shares=512 -v /srv/watchtogether/movies:/root/watchtogether/static/movies watchtogether:latest celery
podman run -dt --pod watchtogether --name watchtogether-redis redis:latest

for container in $containers; do
	podman generate systemd -n ${container} > /etc/systemd/system/container-${container}.service
done

systemctl daemon-reload

for container in $containers; do
	systemctl enable --now container-$container
done
```

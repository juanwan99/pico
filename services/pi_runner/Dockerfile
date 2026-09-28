# pi-runner: starts per-session workspace boxes (card #1093).
# Pico-trusted; holds the docker socket. Never runs model input itself —
# model commands only ever execute inside the gVisor workspace box.
FROM python:3.12-slim-bookworm

ARG DOCKER_CLI_VERSION=29.4.0
# sha256 of docker-29.4.0.tgz (download.docker.com == mirrors.aliyun.com, 2026-09-28)
ARG DOCKER_CLI_SHA256=56c90317a05d86bd84f2bf8d086faefce6f31f82e8c92880de7710dd5f8ce5b7
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/services \
    DOCKER_CONFIG=/tmp/.docker

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl; \
    curl -fsSL -o /tmp/docker.tgz \
      "https://mirrors.aliyun.com/docker-ce/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz"; \
    echo "${DOCKER_CLI_SHA256}  /tmp/docker.tgz" | sha256sum -c -; \
    tar -xzf /tmp/docker.tgz -C /tmp docker/docker; rm -f /tmp/docker.tgz; \
    mv /tmp/docker/docker /usr/local/bin/docker; \
    docker --version; \
    apt-get purge -y curl; apt-get autoremove -y; rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
      "fastapi>=0.115,<1" "uvicorn[standard]>=0.32,<1" "httpx>=0.27,<1"

WORKDIR /app
COPY services/pi_runner /app/services/pi_runner
CMD ["python", "-m", "pi_runner"]

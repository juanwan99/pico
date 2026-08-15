# pico-sandbox sidecar — process-separated from pico-api / LibreChat.
# Headless Playwright Chromium. Unprivileged container. Does not bind product UI or pico-api ports.
# Session profiles live under /tmp (tmpfs at runtime), never the host home dir.
# Pin bookworm: floating python:3.12-slim is Debian trixie, where
# `playwright install --with-deps` still asks for ttf-unifont /
# ttf-ubuntu-font-family (removed). Bookworm still has those packages.
FROM python:3.12-slim-bookworm

WORKDIR /app
ARG PICO_GIT_SHA=unknown
ENV PICO_GIT_SHA=${PICO_GIT_SHA} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/services:/app/services/orchestrator \
    PICO_SANDBOX_HOST=0.0.0.0 \
    PICO_SANDBOX_PORT=18767 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    HOME=/tmp/pico-sandbox-home \
    XDG_CONFIG_HOME=/tmp/pico-sandbox-home/.config \
    XDG_CACHE_HOME=/tmp/pico-sandbox-home/.cache \
    PICO_SANDBOX_PROFILE_ROOT=/tmp/pico-sandbox-profiles

RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ --upgrade pip

COPY requirements.txt /app/requirements.txt
RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ -r /app/requirements.txt \
    && pip install -i https://mirrors.aliyun.com/pypi/simple/ playwright==1.52.0

# Chromium + OS deps baked into the sidecar image (not host Chrome).
# Rewrite Debian apt to Aliyun so China ECS can install --with-deps.
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; \
      sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list; \
      sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list; \
    fi; \
    playwright install --with-deps chromium; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      xvfb scrot xdotool \
      libreoffice-writer libreoffice-calc libreoffice-impress \
      fonts-wqy-zenhei fonts-liberation; \
    rm -rf /var/lib/apt/lists/*; \
    chmod -R a+rX /opt/ms-playwright

COPY services /app/services

RUN useradd --create-home --uid 65532 --shell /usr/sbin/nologin sandbox \
    && mkdir -p /tmp/pico-sandbox-home /tmp/pico-sandbox-profiles /var/lib/pico/teacher-disks \
    && chown -R 65532:65532 /app /tmp/pico-sandbox-home /tmp/pico-sandbox-profiles /opt/ms-playwright /var/lib/pico/teacher-disks

USER 65532:65532
EXPOSE 18767
CMD ["python", "-m", "sandbox_worker"]

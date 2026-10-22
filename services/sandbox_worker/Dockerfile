# pico-sandbox sidecar — process-separated from pico-api / LibreChat.
# Headless Playwright Chromium. Unprivileged container. Does not bind product UI or pico-api ports.
# Session profiles live under /tmp (tmpfs at runtime), never the host home dir.
# Pin bookworm: floating python:3.12-slim is Debian trixie, where
# `playwright install --with-deps` still asks for ttf-unifont /
# ttf-ubuntu-font-family (removed). Bookworm still has those packages.
# Pin the digest too: a tag-only FROM rebuilt every pip/apt layer on each
# deploy (#1200; same cache law as Dockerfile.pico-api.true-pi).
FROM python:3.12-slim-bookworm@sha256:9c47360a2a0355e2da18516d0b1c2126ec22c195d2185e97347c9d98398c5bef

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
    && pip install -i https://mirrors.aliyun.com/pypi/simple/ playwright==1.63.0

# pico-office (same image, second service): office scripts get a full Python.
# Mature PyPI only; not a science stack. requests is pointless (network none).
RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ \
      "pandas>=2.2,<3" "Pillow>=10,<12" "matplotlib>=3.8,<4"

# Chromium + OS deps baked into the sidecar image (not host Chrome).
# Rewrite Debian apt to Aliyun so China ECS can install --with-deps.
# Browsers from npmmirror: cdn.playwright.dev → Google storage stalls at 0% from
# ECS (edu-core#3509 deploy, 10-21); the mirror serves the same paths at ~13 MB/s.
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; \
      sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list; \
      sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list; \
    fi; \
    PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright \
      playwright install --with-deps chromium; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      xvfb scrot xdotool \
      libreoffice-writer libreoffice-calc libreoffice-impress \
      fonts-wqy-zenhei fonts-liberation; \
    rm -rf /var/lib/apt/lists/*; \
    chmod -R a+rX /opt/ms-playwright

# Fonts (pico#1295). Playwright's deps bring one CJK font in one weight
# (WenQuanYi); "宋体" in a teacher's Word file matched a Latin font and bold
# Chinese could not render. Noto CJK = Song + Hei in Regular/Bold, UKai = Kai,
# Carlito/Caladea = Calibri/Cambria metrics, DejaVu = math symbols.
# The conf maps Windows/Mac names to these; matplotlib defaults to Chinese.
COPY --chmod=0644 services/sandbox_worker/fonts/24-pico-cjk.conf services/sandbox_worker/fonts/64-pico-cjk-fallback.conf /etc/fonts/conf.d/
COPY --chmod=0644 services/sandbox_worker/fonts/mpl_cjk_defaults.py /tmp/mpl_cjk_defaults.py
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      fonts-noto-cjk fonts-arphic-ukai fonts-crosextra-carlito fonts-crosextra-caladea fonts-dejavu-core; \
    rm -rf /var/lib/apt/lists/*; \
    fc-cache -f; \
    python /tmp/mpl_cjk_defaults.py; \
    rm /tmp/mpl_cjk_defaults.py

COPY services /app/services

# Official mermaid UMD (pin in mermaid_pin.py). No runtime CDN.
RUN python -m sandbox_worker.fetch_mermaid --dest /opt/pico/vendor/mermaid.min.js \
    && chmod -R a+rX /opt/pico

ENV PICO_MERMAID_JS_PATH=/opt/pico/vendor/mermaid.min.js

RUN useradd --create-home --uid 65532 --shell /usr/sbin/nologin sandbox \
    && mkdir -p /tmp/pico-sandbox-home /tmp/pico-sandbox-profiles /var/lib/pico/teacher-disks \
    && chown -R 65532:65532 /app /tmp/pico-sandbox-home /tmp/pico-sandbox-profiles /opt/ms-playwright /var/lib/pico/teacher-disks

USER 65532:65532
EXPOSE 18767
CMD ["python", "-m", "sandbox_worker"]

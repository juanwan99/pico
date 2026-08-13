# pico-sandbox sidecar — process-separated from pico-api / LibreChat.
# NOT privileged. Does not bind 8080 / 18088 / 18765.
# Chromium/Playwright may be added later; userspace egress (web_guard) is required either way.
FROM python:3.12-slim

WORKDIR /app
ARG PICO_GIT_SHA=unknown
ENV PICO_GIT_SHA=${PICO_GIT_SHA} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/services:/app/services/orchestrator
    PICO_SANDBOX_HOST=0.0.0.0 \
    PICO_SANDBOX_PORT=18767

RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ --upgrade pip

COPY requirements.txt /app/requirements.txt
RUN pip install -i https://mirrors.aliyun.com/pypi/simple/ -r /app/requirements.txt

COPY services /app/services

RUN useradd --create-home --uid 65532 --shell /usr/sbin/nologin sandbox \
    && mkdir -p /tmp/pico-sandbox \
    && chown -R 65532:65532 /tmp/pico-sandbox

USER 65532:65532
EXPOSE 18767
CMD ["python", "-m", "sandbox_worker"]

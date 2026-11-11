# Workspace box for true Pi with builtins ON (card #1093).
# Runs under gVisor via pi-runner; one container per conversation turn.
# Base = pico-sandbox (Python office libs, LibreOffice, Chromium, CJK fonts)
# so the layers are shared with the office sidecar already on the host.
# Adds Node + pinned Pi + the Pico gateway extension. No secrets in the image.
ARG BASE=pico-sandbox:v13
FROM ${BASE}

ARG NODE_VERSION=22.22.0
USER root
ENV PATH="/usr/local/lib/nodejs/bin:${PATH}" \
    HOME=/home/pi \
    XDG_CONFIG_HOME=/home/pi/.config \
    XDG_CACHE_HOME=/home/pi/.cache \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NPM_CONFIG_REGISTRY=https://registry.npmmirror.com \
    NPM_CONFIG_PREFIX=/home/pi/.npm-global \
    OPENBLAS_NUM_THREADS=2 \
    OMP_NUM_THREADS=2 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    PYTHONPATH=

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      ca-certificates curl xz-utils git unzip zip poppler-utils file jq; \
    curl -fsSL \
      "https://npmmirror.com/mirrors/node/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
      -o /tmp/node.tar.xz; \
    mkdir -p /usr/local/lib/nodejs; \
    tar -xJf /tmp/node.tar.xz -C /usr/local/lib/nodejs --strip-components=1; \
    rm -f /tmp/node.tar.xz; \
    NPM_CONFIG_PREFIX=/usr/local/lib/nodejs npm install -g @earendil-works/pi-coding-agent@0.84.4; \
    pi --version; \
    rm -rf /var/lib/apt/lists/* /root/.npm

# Reading helpers the model reaches for first (PDF / old Excel).
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ \
      "pypdf>=4,<6" "pdfplumber>=0.11,<1" "xlrd>=2,<3"

COPY services/true_pi_bridge /opt/pico/true_pi_bridge
# Base image's sandbox dirs are not used in a box; drop them so nothing
# looks like a host path from inside.
RUN chmod -R a+rX /opt/pico/true_pi_bridge \
 && rm -rf /var/lib/pico /app \
 && mkdir -p /workspace /memory /home/pi \
 && chown 65532:65532 /workspace /memory /home/pi

# Warm Pi's boot caches once at build (edu-core#5227): jiti's transpiled
# extensions + Node's compile cache, for every extension the runner may load.
# pi-boot copies them into each box's tmpfs /tmp (same paths, same image).
COPY services/pi_workspace/pi-boot /opt/pico/pi-boot
USER 65532:65532
RUN set -eux; \
    B=/opt/pico/true_pi_bridge; \
    (echo '{"type":"get_state"}'; sleep 5) \
      | NODE_COMPILE_CACHE=/tmp/node-cc timeout 60 pi --mode rpc \
          --no-context-files --no-extensions --provider openai --model warm \
          -e $B/pico-gateway-tools.ts -e $B/look-cap.ts \
          -e $B/vendor/pi-0.73.1/plan-mode/index.ts \
          -e $B/vendor/pi-mem-1.2.0/index.ts > /tmp/warm.out; \
    grep -q '"type"' /tmp/warm.out; \
    test -n "$(ls -A /tmp/jiti)"; test -n "$(ls -A /tmp/node-cc)"; \
    rm -f /tmp/warm.out
USER root
RUN mkdir -p /opt/pico/boot-cache \
 && mv /tmp/jiti /tmp/node-cc /opt/pico/boot-cache/ \
 && chmod -R a+rX /opt/pico/boot-cache \
 && chmod 0755 /opt/pico/pi-boot \
 && rm -rf /home/pi && mkdir -p /home/pi && chown 65532:65532 /home/pi \
 && du -sh /opt/pico/boot-cache/*

USER 65532:65532
WORKDIR /workspace
ENTRYPOINT ["/opt/pico/pi-boot"]
CMD ["pi", "--version"]

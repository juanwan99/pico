"""Pinned official mermaid UMD. Not a Pico layout engine."""

MERMAID_VERSION = "11.15.0"

# China ECS first, then public CDNs. Same pin on every URL.
MERMAID_URLS: tuple[str, ...] = (
    f"https://registry.npmmirror.com/mermaid/{MERMAID_VERSION}/files/dist/mermaid.min.js",
    f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/mermaid.min.js",
    f"https://unpkg.com/mermaid@{MERMAID_VERSION}/dist/mermaid.min.js",
)

# mermaid 11 UMD is a few MB. Reject empty / HTML error pages.
MERMAID_MIN_BYTES = 400_000
MERMAID_MAX_BYTES = 8_000_000

DEFAULT_MERMAID_PATH = "/opt/pico/vendor/mermaid.min.js"

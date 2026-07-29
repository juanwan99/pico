#!/usr/bin/env bash
# Deprecated name: same as run-product (NextChat product shell).
set -euo pipefail
exec bash "$(cd "$(dirname "$0")" && pwd)/run-product.sh"

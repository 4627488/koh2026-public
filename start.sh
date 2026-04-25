#!/bin/bash
# Asuri Major 服务启动脚本
# 在容器内 PATH 已包含 .venv/bin，直接调用 python 即可
set -euo pipefail

APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${APP_ROOT}/src:${PYTHONPATH:-}"
exec python -m koh

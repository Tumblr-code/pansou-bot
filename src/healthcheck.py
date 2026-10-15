"""Docker HEALTHCHECK：内置模式下检查本机后端，外部模式直接通过。"""
import json
import os
import sys
import urllib.request

if os.environ.get("PANSOU_BACKEND", "external").lower() != "builtin":
    sys.exit(0)
port = os.environ.get("BACKEND_PORT", "8888")
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=5) as response:
        sys.exit(0 if json.load(response).get("status") == "ok" else 1)
except Exception:
    sys.exit(1)

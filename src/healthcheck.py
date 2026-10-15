"""Docker HEALTHCHECK：检查本机搜索引擎。"""
import json
import os
import sys
import urllib.request

port = os.environ.get("ENGINE_PORT", "8888")
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=5) as response:
        sys.exit(0 if json.load(response).get("status") == "ok" else 1)
except Exception:
    sys.exit(1)

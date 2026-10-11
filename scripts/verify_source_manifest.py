#!/usr/bin/env python3
"""Check the runtime source against docs/SOURCE_MANIFEST.json.

The manifest lists main.py, requirements.txt and every file under src/ with its SHA256,
so a release can be traced to exact source. Run with --update after changing runtime code.
"""
import argparse
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
path = root / "docs/SOURCE_MANIFEST.json"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--update", action="store_true", help="rewrite the manifest from the working tree")
args = parser.parse_args()

names = {str(p.relative_to(root)) for p in (root / "src").rglob("*.py")}
names.update({"main.py", "requirements.txt"})
actual = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in sorted(names)}
if args.update:
    path.write_text(json.dumps({"schema": 2, "runtime_kind": "python", "files": actual},
                               indent=2, sort_keys=True) + "\n")
    print(f"Source manifest updated: {len(actual)} files")
    raise SystemExit(0)
expected = json.loads(path.read_text())["files"]
errors = []
if set(actual) != set(expected):
    errors.append("runtime path set differs: " + ", ".join(sorted(set(actual) ^ set(expected))))
errors += ["runtime hash differs: " + name for name, digest in expected.items()
           if actual.get(name) not in (None, digest)]
if errors:
    raise SystemExit("\n".join(errors) + "\nrun scripts/verify_source_manifest.py --update if the change is intended")
print(f"Source manifest verified: {len(expected)} files")

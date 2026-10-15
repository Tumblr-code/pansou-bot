#!/bin/sh
# 把镜像自带的后端版本更新为上游 main 的最新提交（或指定提交）。
# 用法：scripts/bump_backend.sh [SHA]
set -eu
cd "$(dirname "$0")/.."
. backend/UPSTREAM
revision=${1:-$(git ls-remote "$PANSOU_REPOSITORY" refs/heads/main | cut -f1)}
echo "$revision" | grep -Eq '^[0-9a-f]{40}$' || { echo "bad revision: $revision" >&2; exit 1; }
sed -i.bak "s/^PANSOU_REVISION=.*/PANSOU_REVISION=$revision/" backend/UPSTREAM && rm -f backend/UPSTREAM.bak
echo "backend pinned to $revision"

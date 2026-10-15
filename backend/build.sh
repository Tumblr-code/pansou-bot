#!/bin/sh
# 从上游源码构建 PanSou 后端，输出可直接运行或打包发布的目录：
#   pansou          静态链接的可执行文件
#   defaults.env    上游 Dockerfile 里的默认环境变量（频道、插件列表等）
#   VERSION.json    上游提交号与提交时间
#   LICENSE         上游许可证
#
# 用法：build.sh --arch amd64|arm64 --out DIR [--revision SHA] [--repository URL]
# 不指定 --revision 时使用 backend/UPSTREAM 里固定的版本。需要 git 和 go。
set -eu

here=$(cd "$(dirname "$0")" && pwd)
. "$here/UPSTREAM"
repository=$PANSOU_REPOSITORY
revision=$PANSOU_REVISION
arch=
out=

while [ $# -gt 0 ]; do
    case $1 in
        --arch) arch=$2; shift 2 ;;
        --out) out=$2; shift 2 ;;
        --revision) revision=$2; shift 2 ;;
        --repository) repository=$2; shift 2 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done
case $arch in amd64|arm64) ;; *) echo "--arch must be amd64 or arm64" >&2; exit 2 ;; esac
[ -n "$out" ] || { echo "--out is required" >&2; exit 2; }
echo "$revision" | grep -Eq '^[0-9a-f]{40}$' || { echo "revision must be a full commit SHA" >&2; exit 2; }

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

git -c init.defaultBranch=main init -q "$work/src"
git -C "$work/src" fetch -q --depth 1 "$repository" "$revision"
git -C "$work/src" checkout -q FETCH_HEAD
committed_at=$(git -C "$work/src" log -1 --format=%cI)

mkdir -p "$out"
(
    cd "$work/src"
    CGO_ENABLED=0 GOOS=linux GOARCH=$arch GOTOOLCHAIN=auto GOFLAGS=-mod=readonly \
        go build -trimpath -ldflags="-s -w" -o "$out/pansou" .
)

# 取出运行阶段 ENV 指令里的 KEY=VALUE（值里没有空格），端口和缓存目录由机器人设置
awk '
    !inenv && /^ENV[ \t]/ { inenv = 1; buf = ""; sub(/^ENV[ \t]+/, "") }
    inenv {
        line = $0
        more = (line ~ /\\[ \t]*$/)
        sub(/\\[ \t]*$/, "", line)
        buf = buf " " line
        if (!more) {
            n = split(buf, parts, /[ \t]+/)
            for (i = 1; i <= n; i++) if (parts[i] ~ /^[A-Z_][A-Z0-9_]*=/) print parts[i]
            inenv = 0
        }
    }
' "$work/src/Dockerfile" | grep -Ev '^(PORT|CACHE_PATH)=' > "$out/defaults.env" || true

cp "$work/src/LICENSE" "$out/LICENSE"
printf '{\n  "revision": "%s",\n  "committed_at": "%s",\n  "source": "%s"\n}\n' \
    "$revision" "$committed_at" "$repository" > "$out/VERSION.json"

echo "built $revision ($committed_at) for linux/$arch -> $out"

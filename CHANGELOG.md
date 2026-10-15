# 更新日志

所有项目的显著变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [3.0.0] - 2026-10-15

项目改名为 **PanSou Bot**（仓库 `Tumblr-code/pansou-bot`，原 `tg-pansou-bot`），PanSou 搜索引擎和 Telegram 机器人整合为一个项目、一个 Docker 镜像，不再需要单独部署任何服务。

### Added

- 镜像自带从上游 fish2018/pansou 源码编译的搜索引擎，由程序自己启动、健康检查、崩溃重启和关闭
- 在线升级：`/upgrade` 从 GitHub Releases 下载新版搜索引擎，核对 SHA256、通过健康检查后才切换，失败自动恢复；`/upgrade rollback` 回滚；升级后的版本连续崩溃时自动退回
- `/status` 显示搜索引擎版本、运行时长和上一个版本
- 定时检查新版本并私信管理员（`UPGRADE_CHECK_HOURS`），可选全自动升级（`AUTO_UPGRADE`）
- Engine release 工作流每天跟踪上游，编译 amd64/arm64 并附带构建来源证明发布
- Image 工作流发布 `ghcr.io/tumblr-code/pansou-bot` 多架构镜像；CI 在镜像里实际启动一次搜索引擎

### Changed

- Docker 运行方式改为单容器、桥接网络，不映射任何端口
- `CHANNELS`、`ENABLED_PLUGINS` 默认值跟随所运行的搜索引擎版本

### Removed

- 不再支持连接单独部署的 PanSou：`PANSOU_API_URL`、`PANSOU_API_TOKEN` 已移除
- systemd 单元、端口守卫脚本、源码发行包脚本和 `docs/SOURCE_MANIFEST.json`

## 2026-10 生产加固（未单独发版）

### Documentation

- README 与安装运维文档改写为面向所有读者的中英文教程，移除了旧的迁移记录
- 源码清单改为 `docs/SOURCE_MANIFEST.json`，由 `scripts/verify_source_manifest.py` 校验，`--update` 可重新生成

### Hardening

### Added

- 新增原子 release 构建、`current`/`previous` 切换和失败自动回滚脚本
- 新增 `tgpansou`、`pansou` 专用用户的 systemd 沙箱单元与 8888 loopback 防火墙守卫
- 新增 Python 3.11/3.12 pytest、Ruff、依赖一致性和 Docker 构建 CI
- 新增搜索并发、排队超时、关键词边界、分阶段 HTTP 超时和只读 `APP_VERSION`

### Changed

- 用户设置迁移至可配置的 `DATA_DIR`，采用 `fsync` + `os.replace` 原子写入；损坏或未知结构文件会先隔离
- 正常关闭由 python-telegram-bot 生命周期管理，并关闭共享 HTTP 客户端与后台任务
- JSON 日志真正应用 `LOG_LEVEL`，只记录耗时、结果数、缓存命中和错误类别等非敏感指标
- 相同搜索请求继续合并并保留 120 秒缓存；等待者取消不会取消共享请求
- 运行依赖按已验证版本精确锁定并缩减为实际运行所需包
- PanSou 沙箱允许其 `bytedance/sonic` 运行时加载器调用 `mprotect`，其余非 root 与 systemd 防护保持不变
- Bot 对 PanSou 使用弱依赖和启动顺序约束，PanSou 独立维护后 Bot 不会被永久停用

### Removed

- 完整移除无人使用的 HTTP API、8090 服务、配置与 `aiohttp` 依赖
- 完整移除 `/update`、Git/PIP 子进程维护逻辑和相关菜单项

### 🔎 Pansou API 适配与来源管理

### Added

- 新增 `/s` 短命令，便于群组中快速搜索
- 新增 `/sources`、`/plugins`、`/channels`、`/reset` 管理命令
- 新增 `/search` 临时参数：`--src`、`--types`、`--plugins`、`--channels`、`--limit`、`--refresh`
- 新增插件和频道筛选设置：`/settings plugins ...`、`/settings channels ...`
- 新增 Telegram 命令菜单同步，启动后自动设置常用 Bot 命令
- 新增对光鸭、腾讯微云、蓝奏云、坚果云等网盘类型的展示和别名归一化

### Changed

- 默认不再向上游传固定 `cloud_types` 白名单，避免 Pansou 新增网盘类型后被 Bot 侧过滤
- 搜索结果兼容 `merged_by_type`、`results`、`items`、`results[].links` 等多种 Pansou API 返回结构
- 搜索结果链接改为 HTML 可点击链接，减少长链接导致的 Telegram 消息过长问题
- `/status` 现在展示 Pansou API 插件和频道数量
- `/refresh` 会同步清理服务信息缓存
- README 和 DEPLOY 补充来源筛选、插件/频道管理、群组短命令和 Pansou API 适配说明

### Fixed

- 修复部分上游网盘类型别名导致结果被归到 `others` 或筛选遗漏的问题
- 修复回调刷新时丢失原搜索参数的问题
- 修复全量结果页和分页详情没有按用户结果数量设置展示的问题

### Removed

- 移除已废弃的外部客服适配层、回调路由、账号查询接口和相关配置项

### 🔐 安全基线与工程化

### Added

- 新增 GitHub Actions CI，包含 secret scan、Python 编译检查、smoke import test 和 Docker build 校验
- 新增 `scripts/secret_scan.py`，阻止 `.env.*` 备份文件和明显的 Telegram Bot Token 被提交
- 新增 `scripts/smoke_test.py`，在不启动真实 Bot 的前提下验证核心模块可导入
- 新增 `REQUIRE_HTTP_API_TOKEN` 配置项，用于显式控制 HTTP API 是否允许无令牌访问

### Changed

- `api_main.py` 在安全模式下若未配置 `HTTP_API_TOKEN` 会直接拒绝启动
- `src/http_api.py` 默认改为要求令牌鉴权，只有显式关闭安全模式时才允许匿名访问
- `src/bot.py` 抽出统一搜索流程，减少普通搜索与回调重搜之间的重复逻辑
- `.gitignore` 增强为忽略 `.env.*` 和 `.env.backup*` 变体，避免敏感文件误提交
- README 与 `.env.example` 补充 HTTP API 安全默认值和本地检查说明

### Fixed

- 移除误加入仓库的 `.env.backup.20260228_200505` 敏感备份文件

## [2.3.0] - 2026-03-19

## [2.2.0] - 2026-03-19

### 🌐 Webhook 接入准备

### Added

- 新增独立 `HTTP API` 入口 `api_main.py`
- 新增 `src/http_api.py`，提供 `/healthz` 和 `/api/pansou/search`
- 新增 `HTTP_API_HOST`、`HTTP_API_PORT`、`HTTP_API_TOKEN` 配置项
- 新增结构化 JSON 搜索输出，便于 Webhook 和站点页面复用

### Changed

- README 和 `.env.example` 补充 HTTP API 启动方式、鉴权方式和请求示例
- 搜索能力从纯 Telegram 交互扩展为可复用的本地服务层

## [2.1.0] - 2026-03-18

### 🚀 稳定性与运维升级

### Added

- 新增管理员命令 `/refresh`，用于刷新运行时缓存、限流记录和健康检查状态
- 新增管理员命令 `/update`，支持拉取 GitHub 最新代码、按需安装依赖并自动重启机器人
- 新增搜索请求并发合并机制，相同查询会复用同一次上游请求
- 新增上游搜索结果短时缓存，热门查询可直接命中缓存
- 新增健康检查短缓存，避免频繁探活拖慢响应
- 新增每用户滑动窗口限流，减少高频请求对上游服务的冲击

### Changed

- 搜索缓存 TTL 改为基于单调时钟，避免系统时间变化导致缓存判断异常
- 搜索结果请求量改为按实际显示需求控制，降低单次查询对上游 API 的压力
- 回调按钮处理逻辑重构，确保群聊场景下只能操作自己发起的搜索结果
- 帮助文档与 README 补充维护命令说明和管理员 ID 必填说明

### Fixed

- 修复管理员未配置时默认放开所有高级命令权限的问题
- 修复 Telegram HTML 模式下关键词、用户名、错误信息和搜索结果未转义导致的格式异常
- 修复回调按钮在结果过期、跨用户点击或回调数据解析时的状态不一致问题
- 修复 `rate_limit_per_minute` 配置存在但未实际生效的问题

## [1.1.0] - 2026-03-13

### ⚡ 性能优化

### Changed

- **HTTP 客户端优化**
  - 采用单例模式复用 HTTP 客户端，避免重复创建连接
  - 连接池大小从 10/20 提升到 20/50
  - 启用 HTTP/2 支持，减少网络延迟
  - 优化超时配置：连接超时 5s，读取超时 30s

- **重试机制优化**
  - 实现指数退避重试策略 (0.5s → 1s → 2s → 5s)
  - 新增 `RemoteProtocolError` 异常处理
  - 重试次数从 2 次提升到 3 次

- **缓存系统优化**
  - 新增 LRU 缓存类，支持 TTL 自动过期
  - 缓存大小限制为 50 条，防止内存泄漏
  - 缓存有效期 5 分钟自动清理

- **Bot 配置优化**
  - 连接池大小从 16 提升到 32
  - 优化各超时参数配置

### Fixed

- 修复网络不稳定时频繁断开连接的问题
- 修复长时间运行后内存占用过高的问题
- 修复缓存无限制增长导致的性能下降

## [1.0.0] - 2026-02-26

### 🎉 初始发布

### Added

- 🔍 智能网盘资源搜索功能
- 💬 支持私聊和群组使用
- 📁 支持多种网盘类型（百度、阿里、夸克、天翼等）
- 🔄 搜索结果刷新功能
- ⚡ 异步处理，快速响应
- 🐳 Docker 部署支持
- 📝 详细的部署文档和教程

### 支持的网盘

- 百度网盘
- 阿里云盘
- 夸克网盘
- 天翼云盘
- UC网盘
- 移动云盘
- 115网盘
- PikPak
- 迅雷网盘
- 123网盘
- 磁力链接
- 电驴链接

---

Made with ❤️ by TG Pansou Bot Team

# 安全报告 / Security reporting

请通过仓库 GitHub 的私密漏洞报告功能（若已启用）联系维护者；否则先提交不含漏洞细节或秘密的 issue 请求私密沟通渠道。不要在公开 issue、PR、日志或截图中上传真实 Token、环境文件、用户设置、缓存内容、数据库或可利用的生产细节。PanSou 后端本身的漏洞请报告给上游 [fish2018/pansou](https://github.com/fish2018/pansou)。

Use GitHub private vulnerability reporting when enabled. Otherwise open a minimal issue requesting a private contact channel without disclosing exploit details or secrets. Never publish real tokens, environment files, user settings, cache contents, databases or actionable production details. Report vulnerabilities in the PanSou backend itself to upstream [fish2018/pansou](https://github.com/fish2018/pansou).

复现应使用隔离环境和模拟数据；不向真实用户发消息，不修改线上状态。报告受影响版本、最小复现、影响和脱敏证据。若凭据已泄露，由所有者轮换；删除分支不等于清除历史秘密。

Reproduce with isolated services and synthetic data, without messaging real users or changing production. Include the affected revision, minimal reproduction, impact and redacted evidence. Owners must rotate exposed credentials; branch deletion does not erase secrets from history.

## 在线升级的信任模型 / Trust model of online upgrades

`/upgrade` 只有管理员能用，只从 `BACKEND_UPDATE_REPO`（默认本仓库）的 GitHub Releases 下载，经 HTTPS 获取，核对同一发布里的 `SHA256SUMS`，并只解出四个固定文件名的普通文件。SHA256 防止传输损坏，不防止仓库本身被攻破；每个发布另有 GitHub 构建来源证明，可用 `gh attestation verify <文件> -R Tumblr-code/pansou-bot` 确认它由本仓库的工作流从上游源码构建。不信任在线升级时，设 `BACKEND_UPDATE_CHECK_HOURS=0` 且不使用 `/upgrade`，只靠自己构建的镜像升级。

`/upgrade` is admin-only, downloads only from GitHub Releases of `BACKEND_UPDATE_REPO` (this repository by default) over HTTPS, verifies the `SHA256SUMS` of the same release, and extracts only four regular files with fixed names. SHA256 guards against corruption, not against a compromised repository; every release also carries a GitHub build provenance attestation, which `gh attestation verify <file> -R Tumblr-code/pansou-bot` checks to confirm it was built from upstream source by this repository's workflow. If you do not trust online upgrades, set `BACKEND_UPDATE_CHECK_HOURS=0`, do not use `/upgrade`, and upgrade only through images you build yourself.

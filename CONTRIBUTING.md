# 贡献 / Contributing

欢迎提交 issue 和 PR。请先阅读 README 和[安装与运维教程](docs/OPERATIONS.zh-CN.md)。使用短期分支和 PR，CI 全部通过并完成审查后合入 main，随后删除已合并的分支。不要用真实用户或真实 Token 做测试，CI 只使用模拟数据。

Issues and pull requests are welcome. Read the README and the [operations guide](docs/OPERATIONS.en.md) first. Work on a short-lived branch, open a PR, and merge once every check passes and the change is reviewed; then delete the merged branch. Never test with real users or a real token: CI uses mocked data only.

提交前运行 README「开发」一节的命令。后端代码来自上游 [fish2018/pansou](https://github.com/fish2018/pansou)，本仓库不修改它：后端的问题和改进请提交到上游；这里只负责编译、打包、运行和升级。更新镜像自带的后端版本用 `scripts/bump_backend.sh`。修改中英文核心文档时同时更新两种语言。文档面向所有读者，不要写入任何人自己部署环境的主机名、地址、账号等信息；真实环境文件、Token、用户数据、缓存和日志不得进入仓库。

Run the commands in the README's development section before pushing. Backend code comes from upstream [fish2018/pansou](https://github.com/fish2018/pansou) and is not modified here: report backend issues and improvements upstream; this repository only builds, packages, runs and upgrades it. Use `scripts/bump_backend.sh` to move the bundled backend revision. Keep both documentation languages aligned. The documentation is for every reader: leave out host names, addresses, accounts and other details of any particular deployment, and never commit real environment files, tokens, user data, caches or logs.

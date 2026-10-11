# 贡献 / Contributing

欢迎提交 issue 和 PR。请先阅读 README 和[安装与运维教程](docs/OPERATIONS.zh-CN.md)。使用短期分支和 PR，CI 全部通过并完成审查后合入 main，随后删除已合并的分支。不要用真实用户或真实 Token 做测试，CI 只使用模拟数据。

Issues and pull requests are welcome. Read the README and the [operations guide](docs/OPERATIONS.en.md) first. Work on a short-lived branch, open a PR, and merge once every check passes and the change is reviewed; then delete the merged branch. Never test with real users or a real token: CI uses mocked data only.

提交前运行 README「开发」一节的命令。改动 `main.py`、`requirements.txt` 或 `src/` 后，用 `scripts/verify_source_manifest.py --update` 更新源码清单并一并提交。修改中英文核心文档时同时更新两种语言。文档面向所有读者，不要写入任何人自己部署环境的主机名、地址、账号等信息；真实环境文件、Token、用户数据、缓存和日志不得进入仓库。

Run the commands in the README's development section before pushing. After changing `main.py`, `requirements.txt` or `src/`, refresh the manifest with `scripts/verify_source_manifest.py --update` and commit it with the change. Keep both documentation languages aligned. The documentation is for every reader: leave out host names, addresses, accounts and other details of any particular deployment, and never commit real environment files, tokens, user data, caches or logs.

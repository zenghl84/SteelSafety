# 参与贡献

本仓库以根目录的 v1.8 程序为唯一维护入口。先阅读 [README](README.md)、[架构说明](docs/architecture.md) 和相关业务文档，再在独立分支修改。

提交前执行：

```bash
python -m pip install -r requirements-dev.txt
python start.py --check
python -m ruff check .
python -m unittest discover -s tests -v
node scripts/check_frontend.mjs
```

涉及界面时，在 1366×768 和 1536×864 下检查总览、监测、安全评估、预警和知识库页面。涉及公式或数据源时，说明输入来源、单位、缺测与设备状态处理，并为业务变化补充有意义的验证。

PR 应说明具体问题、修改后的行为和实际验证结果。不要提交虚拟环境、缓存、运行日志、临时报告、压缩包、密钥或本地可选资料。新增第三方资源时保留来源及许可说明。

提交 Issue 时提供复现步骤、Python / 操作系统版本、启动命令和相关日志片段；先删除个人信息或凭据。

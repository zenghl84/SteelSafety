# 开发与验证

## 开发环境

推荐 Python 3.12。使用独立 `.venv/`，按根目录 README 创建环境后执行：

```bash
python -m pip install -r requirements-dev.txt
python start.py --check
```

运行依赖只在 `requirements.txt` 中维护；`requirements-dev.txt` 引用它并添加 Ruff。`pyproject.toml` 用于检查配置，本项目目前从源码目录运行，不提供 `pip install .` 的安装包。

## 检查命令

```bash
python -m ruff check .
python -m unittest discover -s tests -v
python -m compileall -q app.py start.py core tests
node scripts/check_frontend.mjs
```

前端语法检查使用 Node.js，无需 `npm install`。业务测试使用 Python 标准库 `unittest`。页面集成测试会实际读取仓库内的模型、工作簿和前端资源，核对完整页面的数据、占位符与模型哈希。

GitHub Actions 的 `ci.yml` 配置了 Ubuntu / Windows、Python 3.10 / 3.12，以及 Node.js 22。CI 只使用仓库文件，不依赖 `.local/`、既有虚拟环境、可选字体或规范 PDF；远端运行结果以 Actions 页面为准。

Action 版本采用官方示例中的 v7，参考 [checkout](https://github.com/actions/checkout)、[setup-python](https://github.com/actions/setup-python) 和 [setup-node](https://github.com/actions/setup-node) 的用法说明。

## 修改位置

| 变更 | 主要文件 |
| --- | --- |
| 布局与样式 | `assets/home/index.html`、`assets/home/style.css` |
| 总览交互与风速 | `assets/home/app.js` |
| 监测数据工作台 | `assets/home/monitoring.js`、`core/monitoring.py` |
| 评分 | `core/assessment.py`、`data/assessment_config.json`、`assets/home/assessment.js` |
| 关键指标 | `core/key_indicators.py`、`data/key_indicators_config.json`、`assets/home/key_indicators.js` |
| 预警中心 | `core/alerts.py`、`assets/home/alerts.js` |
| 三维显示 | `core/viewer.py`、`assets/viewer/viewer.js`、`SiteEnvironment.js` |
| 知识资料 | `static/knowledge/catalog.json`、`assets/home/knowledge.js` |

业务修改需保留来源、时间、单位和设备状态。变更评分或筛查规则时，同步更新业务测试和说明；不要用零填补缺测，也不要把演示参数混入有效评分。

## 提交范围

提交源码、所需项目数据、配置、文档和测试。`.venv/`、`.local/`、`.logs/`、缓存、压缩包和可选本地资料均由 `.gitignore` 排除。

如需升级 Three.js，成套替换兼容的模块并保留许可证；如需替换 Gen 模型，同步准备匹配的测点映射和 CS19 应力快照。版本变更同步更新 `VERSION` 与 `CHANGELOG.md`。

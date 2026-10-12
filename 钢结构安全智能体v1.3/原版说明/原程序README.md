本包已更新为实测驱动重构版本。请先阅读《实测驱动重构_使用说明.md》，使用完整项目运行。以下为原版项目背景说明。

# 大跨钢结构安全智能体 第一版

## Windows 启动
1. 完整解压 ZIP，勿在压缩包内直接运行。
2. 双击 START_WINDOWS.bat。首次会检查 Python 3.12.8 并安装依赖，需要网络。
3. 浏览器打开终端显示的 Local URL，通常 http://localhost:8501 。保持终端开启。
4. 如果没有找到 Python 3.12.8，使用你的实际解释器路径在此文件夹运行：

```bat
"C:\Users\Administrator\AppData\Roaming\Accio\pre-install\python\python.exe" -m pip install -r requirements.txt
"C:\Users\Administrator\AppData\Roaming\Accio\pre-install\python\python.exe" -m streamlit run app.py
```

本软件也可使用其他兼容 Python 版本手动启动；批处理按用户要求固定检查 3.12.8。

## 已实现
- 内置用户提供的 分类出图.mgt 原始模型。
- 真实三维杆系、旋转缩放、悬停信息、按编号高亮查询。
- 材料和截面筛选；材料或单元类型分类配色。
- 17 个施工阶段按 AELEM/DELEM 累计显示活动单元，提供原始阶段设置。
- CSV 历史应变与温度导入、字段与重复数据检查、测点选择及曲线。
- 模型清单下载、本地状态查询。

## 明确边界
这是独立 Streamlit 首版，使用与住境智核相同的技术路线，未覆盖原住宅项目。
几何来源真实；不生成虚构监测值、安全评分或计算结果。颜色不代表安全等级。
阶段切换仅展示活动单元，不求解支撑、内力、变形或施工历史效应。
尚未实现测点空间映射、实时数据库、温度补偿、误差评估、POD代理、模型修正、MIDAS调用和大语言模型。
MGT读取范围为当前文件的梁/杆/只受拉单元；并非完整 MIDAS 通用解析器。
监测 CSV 为 UTF-8，列为 time,sensor_id,strain_ue,temperature_c；应变με、温度℃，当前会话使用，不写入数据库。
模型坐标换算为米。未提供监测映射时不在三维图中伪造测点。

## 后续所需数据
测点编号、对应单元、安装位置和方向；实测应变温度时间序列；MIDAS工况参数及响应结果。

## 文件
app.py 页面；model.py 解析器；data/model.mgt 原模型；requirements.txt 依赖；START_WINDOWS.bat 启动。

## 字体对比度修复
新增 .streamlit/config.toml 统一深色主题，并提高正文、标签、输入控件、上传区和选项卡对比度。更新后关闭原服务，再双击启动。请完整解压，保留 .streamlit 文件夹。

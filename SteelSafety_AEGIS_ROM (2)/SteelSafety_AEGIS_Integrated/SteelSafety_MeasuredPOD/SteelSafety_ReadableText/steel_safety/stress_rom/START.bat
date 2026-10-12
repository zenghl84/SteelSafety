@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "ROM_PYTHON=python"
python --version >nul 2>&1
if errorlevel 1 set "ROM_PYTHON=py -3"
:menu
echo.
echo CS18 应力降阶代理
echo 1. 安装依赖（首次运行）
echo 2. 查看缺少哪些 MIDAS 结果
echo 3. 训练并检验
echo 4. 打开网页预览
echo 5. 预测倍率 1.05 并导出 CSV
echo 0. 退出
set "ROM_CHOICE="
set /p "ROM_CHOICE=请输入编号："
if "%ROM_CHOICE%"=="0" exit /b
if "%ROM_CHOICE%"=="1" %ROM_PYTHON% -m pip install -r requirements.txt
if "%ROM_CHOICE%"=="2" %ROM_PYTHON% rom.py status
if "%ROM_CHOICE%"=="3" %ROM_PYTHON% rom.py train
if "%ROM_CHOICE%"=="4" %ROM_PYTHON% -m streamlit run preview.py --server.port 8502
if "%ROM_CHOICE%"=="5" %ROM_PYTHON% rom.py predict --lambda-value 1.05
goto menu

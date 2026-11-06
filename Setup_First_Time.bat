@echo off
title First-time setup - Attendance and Engagement App
cd /d "%~dp0"
echo.
echo ============================================================
echo  FIRST-TIME SETUP  (only needed once on a new computer)
echo  Keep the internet ON. This can take 10 to 25 minutes.
echo  Do not close this window until it says SETUP FINISHED.
echo ============================================================
echo.

rem ---- 1. find Python 3.11 ----
set "PYEXE="
set "PYARG="
py -3.11 --version >nul 2>&1 && (set "PYEXE=py" & set "PYARG=-3.11")
if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined PYEXE if exist "%ProgramFiles%\Python311\python.exe" set "PYEXE=%ProgramFiles%\Python311\python.exe"

if not defined PYEXE (
    echo Python 3.11 was not found. Installing it now. Please wait...
    winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
    py -3.11 --version >nul 2>&1 && (set "PYEXE=py" & set "PYARG=-3.11")
    if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    if not defined PYEXE if exist "%ProgramFiles%\Python311\python.exe" set "PYEXE=%ProgramFiles%\Python311\python.exe"
)

if not defined PYEXE (
    echo.
    echo Could not install Python 3.11 automatically.
    echo Please install it from https://www.python.org/downloads/release/python-3119/
    echo ^(tick "Add python.exe to PATH"^), then double-click this file again.
    echo.
    pause
    exit /b 1
)

rem ---- 2. fresh environment ----
echo.
echo [1/6] Creating the environment...
if exist "venv" rmdir /s /q "venv"
"%PYEXE%" %PYARG% -m venv venv
if errorlevel 1 goto :failed

echo.
echo [2/6] Installing the project libraries (large download, be patient)...
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :failed

echo.
echo [3/6] Fixing the camera library...
venv\Scripts\python.exe -m pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless opencv-contrib-python-headless
venv\Scripts\python.exe -m pip install opencv-python==4.11.0.86
if errorlevel 1 goto :failed

echo.
echo [4/6] Fixing the emotion library...
venv\Scripts\python.exe -m pip install tf-keras==2.15.1
if errorlevel 1 goto :failed

echo.
echo [5/6] Downloading the emotion model (needs internet, one time)...
venv\Scripts\python.exe -c "import tf_keras, os; os.environ['TF_USE_LEGACY_KERAS']='1'; import numpy as np; from deepface import DeepFace; DeepFace.analyze(img_path=np.zeros((224,224,3),dtype='uint8'), actions=['emotion'], enforce_detection=False); print('Emotion model ready')"
if errorlevel 1 echo Emotion model download did not finish. It will retry the first time you use Class monitoring.

echo.
echo [6/6] Putting an icon on the Desktop...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Attendance App.lnk'); $s.TargetPath='%~dp0Start_Attendance_App.bat'; $s.WorkingDirectory='%~dp0'; $s.Save()"

echo.
echo ============================================================
echo  SETUP FINISHED.
echo  From now on, double-click  "Attendance App"  on the Desktop
echo  ^(or Start_Attendance_App.bat^) to open the app.
echo ============================================================
echo.
pause
exit /b 0

:failed
echo.
echo Something went wrong. Please take a screenshot of this window and send it for help.
echo.
pause
exit /b 1

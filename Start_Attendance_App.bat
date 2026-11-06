@echo off
title Attendance and Engagement App
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo.
    echo This computer has not been set up yet.
    echo Please double-click  Setup_First_Time.bat  first, then open this file again.
    echo.
    pause
    exit /b 1
)

echo.
echo  Starting the Attendance and Engagement App...
echo  Your browser will open by itself in a few seconds.
echo  KEEP THIS WINDOW OPEN while you use the app.
echo  To stop the app, close this window.
echo.

rem open the browser as soon as the app is ready (runs in the background)
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 90;$i++){try{Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000/ -TimeoutSec 2 | Out-Null; Start-Process 'http://127.0.0.1:5000'; break}catch{Start-Sleep 2}}"

call "venv\Scripts\activate.bat"
python app.py

echo.
echo The app has stopped. If it stopped by mistake, send a screenshot of this window.
pause

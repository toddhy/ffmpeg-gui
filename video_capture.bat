@echo off
REM Navigate to the directory where the script is located
cd /d "%~dp0"

REM Run the Python script
python video_clipper_gui.py

REM If the script crashes, keep the window open so you can see the error
if %ERRORLEVEL% neq 0 (
    echo.
    echo The application closed with an error.
    pause
)

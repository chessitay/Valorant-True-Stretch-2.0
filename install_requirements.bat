@echo off
echo ===========================================
echo   Installing required Python packages...
echo ===========================================

:: Detect Python
where py >nul 2>nul
if %errorlevel%==0 (
    set PYTHON=py
) else (
    set PYTHON=python
)

%PYTHON% -m pip install --upgrade pip
%PYTHON% -m pip install ttkbootstrap pillow

echo.
echo ===========================================
echo   Installation complete! You can now run your script.
echo ===========================================
pause

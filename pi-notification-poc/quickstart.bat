@echo off
REM PI Notification POC - Quick Start Script
REM This script helps you quickly test the application

echo ============================================
echo PI Notification POC - Quick Start
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

echo [OK] Python is installed
echo.

REM Check if we're in the right directory
if not exist "src\main.py" (
    echo ERROR: Please run this script from the pi-notification-poc directory
    pause
    exit /b 1
)

echo [OK] Running from correct directory
echo.

REM Create necessary directories
if not exist "logs" mkdir logs
if not exist "temp_pdfs" mkdir temp_pdfs

echo What would you like to do?
echo.
echo 1. Test installation (check dependencies)
echo 2. Run application in console mode
echo 3. Install as Windows service
echo 4. Start Windows service
echo 5. Stop Windows service
echo 6. View logs
echo 7. Exit
echo.

set /p choice="Enter your choice (1-7): "

if "%choice%"=="1" goto test
if "%choice%"=="2" goto run
if "%choice%"=="3" goto install_service
if "%choice%"=="4" goto start_service
if "%choice%"=="5" goto stop_service
if "%choice%"=="6" goto view_logs
if "%choice%"=="7" goto end

echo Invalid choice
pause
exit /b 1

:test
echo.
echo ============================================
echo Testing Installation
echo ============================================
echo.

echo Testing Python packages...
python -c "import yaml; print('[OK] PyYAML installed')" || goto error
python -c "import PyPDF2; print('[OK] PyPDF2 installed')" || goto error
python -c "import requests; print('[OK] requests installed')" || goto error
python -c "import win32com.client; print('[OK] pywin32 installed')" || goto error
python -c "import PIconnect; print('[OK] PIconnect installed')" 2>nul || echo [WARNING] PIconnect not installed (requires PI SDK)

echo.
echo Testing Ollama connection...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Cannot connect to Ollama at http://localhost:11434
    echo Make sure Ollama service is running
) else (
    echo [OK] Ollama service is running
)

echo.
echo Testing configuration file...
if exist "config\config.yaml" (
    echo [OK] Configuration file found
) else (
    echo [ERROR] Configuration file not found
    echo Please create config\config.yaml from the template
    goto error
)

echo.
echo ============================================
echo Installation test complete!
echo ============================================
pause
exit /b 0

:run
echo.
echo ============================================
echo Running Application in Console Mode
echo ============================================
echo.
echo Press Ctrl+C to stop the application
echo.
python src\main.py
pause
exit /b 0

:install_service
echo.
echo ============================================
echo Installing Windows Service
echo ============================================
echo.
echo NOTE: This requires Administrator privileges
echo.
python src\windows_service.py install
if errorlevel 1 goto error

echo.
echo Service installed successfully!
echo You can now start it using option 4 or via services.msc
pause
exit /b 0

:start_service
echo.
echo ============================================
echo Starting Windows Service
echo ============================================
echo.
python src\windows_service.py start
if errorlevel 1 goto error

echo.
echo Service started successfully!
pause
exit /b 0

:stop_service
echo.
echo ============================================
echo Stopping Windows Service
echo ============================================
echo.
python src\windows_service.py stop
if errorlevel 1 goto error

echo.
echo Service stopped successfully!
pause
exit /b 0

:view_logs
echo.
echo ============================================
echo Application Logs
echo ============================================
echo.

if exist "logs\pi_notification.log" (
    type logs\pi_notification.log
) else (
    echo No logs found. The application hasn't run yet.
)

echo.
pause
exit /b 0

:error
echo.
echo ============================================
echo An error occurred!
echo ============================================
echo.
echo Please check the error messages above
pause
exit /b 1

:end
echo.
echo Goodbye!
exit /b 0

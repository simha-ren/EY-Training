@echo off
REM ProposalForge Pro - Quick Start Script for Windows

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║     ProposalForge Pro - Production Installation Script         ║
echo ║                    Windows Version                             ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

REM Check Python version
echo [1/6] Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo ✗ Python not found. Please install Python 3.11+
    pause
    exit /b 1
)
python --version
echo ✓ Python found
echo.

REM Create virtual environment
echo [2/6] Creating virtual environment...
if not exist "venv" (
    python -m venv venv
    echo ✓ Virtual environment created
) else (
    echo ✓ Virtual environment already exists
)
echo.

REM Activate virtual environment
echo [3/6] Activating virtual environment...
call venv\Scripts\activate.bat
echo ✓ Virtual environment activated
echo.

REM Install dependencies
echo [4/6] Installing dependencies...
python -m pip install --upgrade pip setuptools wheel >nul 2>&1
pip install -r requirements.txt >nul 2>&1
echo ✓ Dependencies installed
echo.

REM Setup environment
echo [5/6] Setting up configuration...
if not exist ".env" (
    copy .env.example .env >nul
    echo ⚠ Created .env file - Please edit with your CLAUDE_API_KEY
    echo   Edit .env and add: CLAUDE_API_KEY=sk-ant-...
) else (
    echo ✓ .env file already exists
)
echo.

REM Create necessary directories
echo [6/6] Creating necessary directories...
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "temp" mkdir temp
echo ✓ Directories created
echo.

REM Final message
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ✓ Installation complete!
echo ╚════════════════════════════════════════════════════════════════╝
echo.
echo Next steps:
echo.
echo 1. Edit your API key:
echo    Open .env in notepad and add your CLAUDE_API_KEY
echo.
echo 2. Run the application (requires 2 Command Prompts):
echo.
echo    Command Prompt 1 - Frontend:
echo    ^> venv\Scripts\activate.bat
echo    ^> streamlit run app_prod.py
echo.
echo    Command Prompt 2 - Backend:
echo    ^> venv\Scripts\activate.bat
echo    ^> python api_server.py
echo.
echo 3. Access the application:
echo    Frontend: http://localhost:8000
echo    API: http://localhost:8001
echo    Docs: http://localhost:8001/docs
echo.
echo Documentation:
echo    Setup: type SETUP.md
echo    Deployment: type DEPLOYMENT.md
echo.
echo Or use Docker:
echo    docker-compose up -d
echo.
pause

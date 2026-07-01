# ProposalForge Pro - Setup & Installation Guide

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Local Installation](#local-installation)
3. [Configuration](#configuration)
4. [Verification](#verification)
5. [Common Issues](#common-issues)
6. [Next Steps](#next-steps)

## System Requirements

### Minimum Requirements

- **OS**: Windows 10+, macOS 10.14+, Ubuntu 18.04+
- **Python**: 3.11 or higher
- **RAM**: 4GB minimum (8GB recommended)
- **Storage**: 2GB free space
- **Network**: Internet connection (for Claude API)

### Required Software

- Git
- Python 3.11+
- pip (included with Python)
- Docker (optional, but recommended for production)

### API Requirements

- Claude API Key from Anthropic (Free tier available)
  - Sign up: https://console.anthropic.com
  - Get free credits: $5 monthly

## Local Installation

### Step 1: Clone Repository

```bash
# Using HTTPS
git clone https://github.com/your-username/proposalforge-pro.git
cd proposalforge-pro

# OR using SSH
git clone git@github.com:your-username/proposalforge-pro.git
cd proposalforge-pro
```

### Step 2: Create Virtual Environment

```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt)
python -m venv venv
venv\Scripts\activate.bat
```

### Step 3: Upgrade pip

```bash
pip install --upgrade pip setuptools wheel
```

### Step 4: Install Dependencies

```bash
# Install required packages
pip install -r requirements.txt

# Verify installation
pip list | grep -E "anthropic|streamlit|fastapi|pydantic"
```

### Step 5: Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit .env file with your settings
# macOS/Linux: use nano, vim, or VS Code
nano .env

# Windows: use Notepad or your favorite editor
notepad .env
```

### Step 6: Set API Key

Edit `.env` file and add your Claude API key:

```bash
CLAUDE_API_KEY=sk-ant-... # Your actual API key
```

**Security Note**: Never commit `.env` to version control!

## Configuration

### Essential Configuration

```bash
# .env file
CLAUDE_API_KEY=sk-ant-xxx...           # Your Claude API key (required)
CLAUDE_MODEL=claude-3-5-sonnet-20241022 # Model to use
APP_ENV=development                     # development | production
```

### Optional Configuration

```bash
# Safety & Compliance
CONFIDENCE_THRESHOLD=0.6                # Confidence threshold (0.0-1.0)
ENABLE_PII_REDACTION=True              # PII/PHI redaction
MAX_PII_TOLERANCE=0                    # Max allowed PII before blocking

# File Processing
MAX_FILE_SIZE_MB=50                     # Max upload size
CHUNK_SIZE=2000                         # Document chunk size

# Database
DATABASE_URL=sqlite:///./data/proposalforge.db  # SQLite (default)
AUDIT_DB_PATH=data/audit.db             # Audit logs location

# Logging
LOG_LEVEL=INFO                          # DEBUG | INFO | WARNING | ERROR
ENABLE_AUDIT_LOGGING=True               # Enable audit trails

# Features
ENABLE_AUTO_SUGGESTIONS=True            # Auto-suggest questions
ENABLE_HUMAN_APPROVAL=True              # Approval workflow
ENABLE_GUARDRAILS=True                  # Safety guardrails
```

### Getting Your Claude API Key

1. Visit https://console.anthropic.com
2. Sign up or log in
3. Create a new API key
4. Copy the key starting with `sk-ant-`
5. Paste in your `.env` file

## Verification

### Test Python Installation

```bash
python --version
# Should show Python 3.11 or higher

python -c "import sys; print(sys.executable)"
# Should show path to your venv Python
```

### Test Claude API Connection

```bash
python -c "
from anthropic import Anthropic
import os
client = Anthropic(api_key=os.getenv('CLAUDE_API_KEY'))
print('✓ Claude API connection successful!')
"
```

### Test Dependencies

```bash
python -c "
import streamlit
import fastapi
import pydantic
print('✓ All dependencies installed!')
"
```

### Quick Functional Test

```bash
python -c "
from core.claude_llm import ClaudeLLMClient
from core.file_processor import FileProcessor
from core.audit_logger import AuditLogger
print('✓ All core modules loaded!')
"
```

## Running the Application

### Terminal Setup

You'll need **two terminals** running simultaneously:

### Terminal 1: Start Streamlit Frontend

```bash
# Make sure you're in the project directory and venv is activated
streamlit run app_prod.py

# You should see:
# Streamlit is running on http://localhost:8000
```

### Terminal 2: Start FastAPI Backend

```bash
# In a new terminal, activate venv first
# macOS/Linux:
source venv/bin/activate

# Windows:
.\venv\Scripts\activate.bat

# Then run the server
python api_server.py

# You should see:
# INFO:     Uvicorn running on http://0.0.0.0:8001
```

### Access Application

- **Frontend**: http://localhost:8000
- **API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs

## Using Docker (Recommended for Production)

### Prerequisites

- Docker installed (https://www.docker.com/products/docker-desktop)
- Docker Compose installed

### Run with Docker Compose

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your settings

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Build Custom Docker Image

```bash
# Build
docker build -t proposalforge-pro:latest .

# Run
docker run -p 8000:8000 -p 8001:8001 \
  -e CLAUDE_API_KEY=sk-ant-... \
  -v $(pwd)/data:/app/data \
  proposalforge-pro:latest
```

## Common Issues & Solutions

### Issue: "ModuleNotFoundError: No module named 'anthropic'"

**Solution:**
```bash
# Make sure venv is activated
# Then reinstall requirements
pip install anthropic --upgrade
```

### Issue: "Port 8000 already in use"

**Solution:**
```bash
# macOS/Linux: Find and kill process
lsof -i :8000
kill -9 <PID>

# Windows: Find and kill process
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Issue: "CLAUDE_API_KEY not found"

**Solution:**
```bash
# Make sure .env file exists
ls -la .env  # macOS/Linux
dir .env    # Windows

# Add API key to .env
echo "CLAUDE_API_KEY=sk-ant-..." >> .env

# Or edit manually with your editor
```

### Issue: "API Key is invalid or expired"

**Solution:**
1. Check API key format (should start with `sk-ant-`)
2. Verify key hasn't been revoked in Anthropic console
3. Check API key has correct permissions
4. Try generating a new key: https://console.anthropic.com

### Issue: "Connection refused on http://localhost:8001"

**Solution:**
```bash
# Make sure FastAPI server is running in Terminal 2
# Check if port 8001 is in use
netstat -an | grep 8001  # macOS/Linux
netstat -ano | findstr :8001  # Windows

# Or try different port
python api_server.py --port 8002
```

### Issue: Streamlit shows "This app has encountered an error"

**Solution:**
```bash
# Check logs for detailed error
streamlit run app_prod.py --logger.level=debug

# Clear Streamlit cache
rm -rf ~/.streamlit  # macOS/Linux
rmdir %USERPROFILE%\.streamlit  # Windows
```

## Database Setup

### SQLite (Default - No Setup Required)

SQLite database is automatically created. No setup needed!

```bash
# Database files created in:
data/audit.db           # Audit logs
data/approvals.db       # Approval requests
sqlite:///./data/proposalforge.db  # Main database
```

### PostgreSQL (Optional - For Production)

```bash
# Install PostgreSQL
# macOS:
brew install postgresql

# Linux (Ubuntu):
sudo apt-get install postgresql

# Windows: Download installer
# https://www.postgresql.org/download/windows/

# Create database
createdb proposalforge

# Update .env
DATABASE_URL=postgresql://user:password@localhost:5432/proposalforge
```

## File Structure Check

After installation, verify your directory structure:

```
proposalforge-pro/
├── venv/                    # Virtual environment
├── core/
│   ├── claude_llm.py       ✓
│   ├── file_processor.py   ✓
│   ├── audit_logger.py     ✓
│   ├── approval_workflow.py ✓
│   ├── report_generator.py ✓
│   └── guardrails.py       ✓
├── data/                    # Will be created
├── logs/                    # Will be created
├── temp/                    # Will be created
├── app_prod.py             ✓
├── api_server.py           ✓
├── requirements.txt        ✓
├── .env                    ✓ (copy from .env.example)
├── .env.example            ✓
├── README.md               ✓
├── DEPLOYMENT.md           ✓
├── Dockerfile              ✓
└── docker-compose.yml      ✓
```

## Next Steps

### 1. Upload Your First Document

1. Open http://localhost:8000
2. Click "📤 Upload & Analyze"
3. Upload a sample PDF, DOCX, or TXT file
4. Click "🔍 Analyze"
5. Wait for Claude to analyze

### 2. Ask Questions

1. Go to "💬 Chat & Questions" tab
2. Ask questions about your document
3. Get Claude-powered answers

### 3. Request Approval

1. Go to "✅ Approval" tab
2. Review the analysis
3. Enter your name and click "Approve & Request Report"

### 4. Download Report

1. Go to "📥 Export" tab
2. Choose format (PDF, DOCX, or JSON)
3. Download your report

### 5. Check Analytics

1. Go to "📊 Analytics" tab
2. View your usage statistics
3. Monitor guardrail triggers

## Advanced Configuration

### Enable Debug Mode

```bash
# In .env
APP_DEBUG=True
LOG_LEVEL=DEBUG

# Then run with debug logging
streamlit run app_prod.py --logger.level=debug
```

### Custom Port Configuration

```bash
# In .env
APP_PORT=8080      # Streamlit port
API_PORT=8081      # FastAPI port

# Then run
streamlit run app_prod.py --server.port 8080
python api_server.py --port 8081
```

### Enable Monitoring

```bash
# In .env
ENABLE_AUDIT_LOGGING=True
LOG_LEVEL=INFO

# Check audit logs
sqlite3 data/audit.db "SELECT * FROM audit_logs LIMIT 10;"
```

## Getting Help

1. **Check Logs**: Review application logs for error details
2. **API Docs**: http://localhost:8001/docs
3. **Claude API Status**: https://status.anthropic.com
4. **Documentation**: See [DEPLOYMENT.md](DEPLOYMENT.md)

## Next: Deployment

Ready to go to production? See [DEPLOYMENT.md](DEPLOYMENT.md) for:
- Azure deployment
- AWS deployment
- Google Cloud deployment
- Heroku deployment
- Docker deployment

---

**Successfully installed ProposalForge Pro!** 🎉

Now run the application and start analyzing documents with Claude AI.

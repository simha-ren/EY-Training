#!/bin/bash
# ProposalForge Pro - Quick Start Script

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     ProposalForge Pro - Production Installation Script         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check Python version
echo -e "${BLUE}[1/6]${NC} Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found. Please install Python 3.11+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found"

# Create virtual environment
echo ""
echo -e "${BLUE}[2/6]${NC} Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${GREEN}✓${NC} Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo -e "${BLUE}[3/6]${NC} Activating virtual environment..."
source venv/bin/activate || . venv/Scripts/activate
echo -e "${GREEN}✓${NC} Virtual environment activated"

# Install dependencies
echo ""
echo -e "${BLUE}[4/6]${NC} Installing dependencies..."
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1
echo -e "${GREEN}✓${NC} Dependencies installed"

# Setup environment
echo ""
echo -e "${BLUE}[5/6]${NC} Setting up configuration..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠${NC} Created .env file - Please edit with your CLAUDE_API_KEY"
    echo -e "   Edit .env and add: CLAUDE_API_KEY=sk-ant-..."
else
    echo -e "${GREEN}✓${NC} .env file already exists"
fi

# Create necessary directories
echo ""
echo -e "${BLUE}[6/6]${NC} Creating necessary directories..."
mkdir -p data logs temp
echo -e "${GREEN}✓${NC} Directories created"

# Final message
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo -e "${GREEN}✓ Installation complete!${NC}"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📝 Next steps:"
echo ""
echo "1. ${YELLOW}Edit your API key:${NC}"
echo "   nano .env  (or use your preferred editor)"
echo "   Add: CLAUDE_API_KEY=sk-ant-..."
echo ""
echo "2. ${YELLOW}Run the application (requires 2 terminals):${NC}"
echo ""
echo "   Terminal 1 - Frontend:"
echo "   $ source venv/bin/activate"
echo "   $ streamlit run app_prod.py"
echo ""
echo "   Terminal 2 - Backend:"
echo "   $ source venv/bin/activate"
echo "   $ python api_server.py"
echo ""
echo "3. ${YELLOW}Access the application:${NC}"
echo "   Frontend: http://localhost:8000"
echo "   API: http://localhost:8001"
echo "   Docs: http://localhost:8001/docs"
echo ""
echo "📚 Documentation:"
echo "   Setup: cat SETUP.md"
echo "   Deployment: cat DEPLOYMENT.md"
echo ""
echo "🐳 Or use Docker:"
echo "   docker-compose up -d"
echo ""

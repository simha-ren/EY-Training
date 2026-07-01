# ProposalForge Pro - Production-Grade Intelligent Document Analysis

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![Claude API](https://img.shields.io/badge/Claude_API-Claude3.5-purple)
![License](https://img.shields.io/badge/license-MIT-blue)

## 🎯 Overview

ProposalForge Pro is an enterprise-grade, AI-powered document analysis platform that leverages Claude AI for intelligent analysis, with built-in guardrails, audit logging, human approval workflows, and comprehensive reporting.

### Key Features

✅ **Claude AI Integration**
- Powered by Claude 3.5 Sonnet for superior analysis
- Intelligent document understanding and insights
- High-confidence analysis with 100% transparency

✅ **Document Analysis**
- Multi-format support (PDF, DOCX, CSV, XLSX, PPTX, TXT)
- Automated objective extraction
- Current challenges identification
- Proposed solutions generation
- Key insights extraction

✅ **Interactive Chat Interface**
- Ask unlimited questions about documents
- Real-time AI-powered responses
- Auto-suggestions for follow-up questions
- Conversation history tracking

✅ **Enterprise Safety**
- PII/PHI redaction (enabled by default)
- Guardrail system for compliance
- Confidence-based validation
- Domain-specific safety checks

✅ **Human Approval Workflow**
- Request-based approval system
- Audit trail for compliance
- Approval status tracking
- Comment annotations

✅ **Professional Reporting**
- PDF report generation
- DOCX document export
- JSON data export
- Customizable report templates
- One-click downloads

✅ **Comprehensive Audit Logging**
- All actions logged automatically
- User activity tracking
- Approval history
- Compliance reporting
- Analytics dashboard

✅ **Production Ready**
- Docker containerization
- Multi-cloud deployment (Azure, AWS, GCP, Heroku)
- FastAPI backend for scalability
- Streamlit frontend for UX
- Error handling & recovery

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Install Python 3.11+
python --version

# Install Git
git --version

# Get Claude API Key
# https://console.anthropic.com
```

### 2. Setup (5 minutes)

```bash
# Clone repository
git clone https://github.com/your-repo/proposalforge-pro.git
cd proposalforge-pro

# Create environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env and add your CLAUDE_API_KEY
```

### 3. Run

```bash
# Terminal 1: Frontend (Streamlit)
streamlit run app_prod.py

# Terminal 2: Backend (FastAPI)
python api_server.py
```

Access:
- 🎨 Frontend: http://localhost:8000
- 🔌 API: http://localhost:8001
- 📚 API Docs: http://localhost:8001/docs

## 📦 Docker Deployment

### Using Docker Compose (Easiest)

```bash
# Copy environment
cp .env.example .env
# Edit .env with your API key

# Run
docker-compose up -d

# Access
# Frontend: http://localhost:8000
# API: http://localhost:8001
```

### Using Docker Directly

```bash
# Build
docker build -t proposalforge-pro:latest .

# Run
docker run -p 8000:8000 -p 8001:8001 \
  -e CLAUDE_API_KEY=sk-ant-... \
  -v $(pwd)/data:/app/data \
  proposalforge-pro:latest
```

## ☁️ Cloud Deployment

### Azure App Service

```bash
az webapp create --resource-group myGroup --plan myPlan --name myApp
az webapp config appsettings set --resource-group myGroup --name myApp \
  --settings CLAUDE_API_KEY=sk-ant-...
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed cloud deployment guides:
- ☁️ Azure App Service
- ☁️ AWS ECS/Fargate
- ☁️ Google Cloud Run
- ☁️ Heroku
- ☁️ DigitalOcean

## 📋 Features in Detail

### 1. Document Upload & Analysis

Upload any document and get instant analysis:
- **Objective**: What the document is about
- **Challenges**: Current problems identified
- **Solutions**: Recommended improvements
- **Insights**: Key takeaways
- **Confidence Score**: Analysis reliability (0-100%)

### 2. Interactive Chat

Ask questions about your document:
- Get AI-powered answers
- Auto-suggested follow-up questions
- Conversation history
- Multi-turn dialogue support

### 3. Guardrails & Safety

Built-in compliance:
- PII/PHI detection & redaction
- Confidence threshold validation
- Policy violation checks
- Domain-specific safety rules

### 4. Human Approval

Enterprise workflow:
- Request-based approval system
- Multi-level approval support
- Approval comments
- Approval history

### 5. Report Generation

Export in multiple formats:
- 📄 PDF (professional layout)
- 📘 DOCX (Word compatible)
- 📊 JSON (data export)
- Includes full analysis + conversation

### 6. Analytics Dashboard

Monitor usage:
- Document upload analytics
- Query patterns
- Guardrail trigger rates
- User activity metrics
- Approval statistics

### 7. Audit Logging

Complete compliance trail:
- All user actions logged
- Timestamps on everything
- User attribution
- Approval chain
- Searchable audit history

## 🔧 Configuration

### Environment Variables

```bash
# Required
CLAUDE_API_KEY=sk-ant-...

# Optional
CLAUDE_MODEL=claude-3-5-sonnet-20241022
CONFIDENCE_THRESHOLD=0.6
ENABLE_PII_REDACTION=True
MAX_FILE_SIZE_MB=50
APP_ENV=production
```

See [.env.example](.env.example) for all options.

## 📊 API Usage

### Upload Document

```bash
curl -X POST http://localhost:8001/api/v1/documents/upload \
  -F "file=@document.pdf" \
  -F "user_id=user123"
```

### Analyze Document

```bash
curl -X POST http://localhost:8001/api/v1/documents/doc-id/analyze \
  -H "Content-Type: application/json" \
  -d '{"document_id":"doc-id","content":"..."}'
```

### Ask Question

```bash
curl -X POST http://localhost:8001/api/v1/documents/doc-id/query \
  -H "Content-Type: application/json" \
  -d '{
    "document_id":"doc-id",
    "query":"What are the main challenges?",
    "context":"..."
  }'
```

### Request Approval

```bash
curl -X POST http://localhost:8001/api/v1/approvals/create \
  -H "Content-Type: application/json" \
  -d '{
    "document_id":"doc-id",
    "analysis":{...},
    "user_id":"user123"
  }'
```

See [API Documentation](http://localhost:8001/docs) for complete API reference.

## 📁 Project Structure

```
proposalforge-pro/
├── app_prod.py                 # Streamlit frontend
├── api_server.py               # FastAPI backend
├── core/
│   ├── claude_llm.py          # Claude integration
│   ├── file_processor.py       # Multi-format file handling
│   ├── audit_logger.py         # Audit logging system
│   ├── approval_workflow.py    # Approval management
│   ├── report_generator.py     # Report generation
│   ├── guardrails.py           # Safety & compliance
│   └── config.py               # Configuration
├── data/
│   ├── audit.db               # Audit logs (SQLite)
│   ├── approvals.db           # Approval requests
│   └── reports/               # Generated reports
├── logs/
│   └── audit.log              # Application logs
├── temp/
│   └── uploads/               # Temporary uploads
├── Dockerfile                  # Docker image
├── docker-compose.yml         # Docker compose
├── requirements.txt           # Python dependencies
├── .env.example               # Environment template
├── DEPLOYMENT.md              # Deployment guide
└── README.md                  # This file
```

## 🔐 Security

### Data Protection

- 🔒 PII/PHI redaction enabled by default
- 🔐 Sensitive data detection
- 🛡️ Guardrail system for compliance
- 📝 Complete audit logging
- ✅ Input validation on all endpoints

### Best Practices

1. **API Keys**: Store in environment variables, never commit
2. **HTTPS**: Enable in production
3. **Authentication**: Add API key validation
4. **Rate Limiting**: Implemented in FastAPI
5. **CORS**: Configure for your domain

## 📈 Performance

- ⚡ Fast Claude API integration
- 🚀 Asynchronous request handling
- 💾 Efficient file processing
- 📦 Optional caching support
- 🌐 Multi-instance ready

## 🐛 Troubleshooting

### Issue: Port Already in Use

```bash
# Find & kill process
lsof -i :8000  # Find
kill -9 <PID>  # Kill
```

### Issue: Claude API Connection Error

```bash
# Verify API key
echo $CLAUDE_API_KEY

# Test connection
python -c "from anthropic import Anthropic; c = Anthropic(); print('OK')"
```

### Issue: Docker Build Fails

```bash
# Clear cache & rebuild
docker-compose build --no-cache
```

## 📚 Documentation

- [Deployment Guide](DEPLOYMENT.md) - Cloud & local deployment
- [API Documentation](http://localhost:8001/docs) - Full API reference
- [Claude API Docs](https://docs.anthropic.com) - Claude integration

## 🤝 Support

For issues or questions:
1. Check [Troubleshooting](#-troubleshooting) section
2. Review [Deployment Guide](DEPLOYMENT.md)
3. Check Claude API [status page](https://status.anthropic.com)

## 📄 License

MIT License - See LICENSE file for details

## 🎯 Roadmap

- [ ] Multi-language support
- [ ] Advanced analytics
- [ ] Custom branding
- [ ] User management
- [ ] SSO integration
- [ ] Advanced approval workflows
- [ ] Mobile app

## 🌟 Credits

- Built with [Claude AI](https://www.anthropic.com)
- Frontend by [Streamlit](https://streamlit.io)
- API by [FastAPI](https://fastapi.tiangolo.com)
- Containerized with [Docker](https://www.docker.com)

---

**ProposalForge Pro** © 2024. Enterprise-Grade Intelligent Document Analysis. 🚀
  ingestion.py         extract · section-aware chunk · domain-tag
  guardrails.py        refusals · disclaimers · PII redaction · gap detection
  generation.py        grounded composer + inline citations (LLM or offline)
  engine.py            orchestrator (the request-time agent loop)
  llm.py               OpenAI/Azure abstraction with offline fallback
domains/*.yaml         per-domain personas, keywords, guardrails, follow-ups
data/<domain>/*.md     seed knowledge base
eval/                  golden_set.json + evaluate.py
```

## Evaluate from the CLI
```bash
python -m eval.evaluate
```

# Murphy System - API Keys Setup Guide

## Required API Keys

### 1. Groq API Key
- **Purpose**: Generative inquiry, command refinement, swarm generation
- **Get from**: https://console.groq.com/keys
- **Environment Variable**: `GROQ_API_KEY`

### 2. Anthropic API Key
- **Purpose**: Claude/Aristotle for deterministic verification
- **Get from**: https://console.anthropic.com/
- **Environment Variable**: `ANTHROPIC_API_KEY`

### 3. OpenAI API Key (Optional)
- **Purpose**: Backup for Groq
- **Get from**: https://platform.openai.com/api-keys
- **Environment Variable**: `OPENAI_API_KEY`

## Setup Instructions

### Option 1: Environment Variables
```bash
export GROQ_API_KEY="your-groq-key-here"
export ANTHROPIC_API_KEY="your-anthropic-key-here"
export OPENAI_API_KEY="your-openai-key-here"  # optional
```

### Option 2: .env File
Create `.env` file in project root:
```
GROQ_API_KEY=your-groq-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
OPENAI_API_KEY=your-openai-key-here
```

### Option 3: Direct Configuration
Edit `murphy_backend_server.py` and add keys directly (not recommended for production):
```python
GROQ_API_KEY = "your-groq-key-here"
ANTHROPIC_API_KEY = "your-anthropic-key-here"
```

## Security Notes
- Never commit API keys to version control
- Use environment variables in production
- Rotate keys regularly
- Monitor usage and costs

## Testing
Once keys are configured, test with:
```bash
python test_llm_integration.py
```

This will verify all LLM providers are accessible.
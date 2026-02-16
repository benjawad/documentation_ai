# Setup Checklist - AI Chatbot

Follow this checklist to ensure everything is properly configured.

## ✅ Prerequisites

- [ ] Python 3.9 or higher installed
- [ ] PostgreSQL 12+ installed and running
- [ ] Redis installed and running
- [ ] Git (for version control)
- [ ] OpenAI API account and API key

## ✅ Installation Steps

### 1. Install Dependencies

```bash
cd c:\Users\Moussa\Desktop\documentation_ai
pip install -r requirements.txt
```

**Verify:**
```bash
pip list | grep -E "langchain|llama-index|pgvector"
```

You should see:
- langchain
- langchain-openai
- langchain-core
- langchain-community
- llama-index
- llama-index-core
- llama-index-llms-openai
- llama-index-embeddings-openai
- llama-index-vector-stores-postgres
- llama-index-vector-stores-redis
- pgvector

### 2. Configure Environment

```bash
# If .env doesn't exist, copy from example
cp .env.example .env
```

**Edit .env and set:**
- [ ] `OPENAI_API_KEY=sk-your-actual-key-here`
- [ ] `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- [ ] `REDIS_HOST`, `REDIS_PORT`
- [ ] `DEFAULT_VECTOR_STORE=postgres` (or redis)

### 3. Database Setup

```bash
# Run migrations
python src/manage.py makemigrations
python src/manage.py migrate
```

**Enable pgvector:**

Option A - Using Django command:
```bash
python src/manage.py setup_pgvector
```

Option B - Using Docker:
```bash
docker-compose exec db psql -U postgres -d ai_analyst -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Option C - Direct PostgreSQL:
```sql
-- Connect to your database
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
SELECT extname FROM pg_extension WHERE extname = 'vector';
```

### 4. Verify Setup

```bash
# Test database connection
python src/manage.py check

# Run health check (if server is running)
curl http://localhost:8000/health/
```

### 5. Index Your Codebase

```bash
# Index with PostgreSQL (recommended)
python src/manage.py index_codebase

# OR with Redis
python src/manage.py index_codebase --use-redis

# Custom path
python src/manage.py index_codebase --path /path/to/your/code
```

**Expected output:**
```
Indexing codebase from: C:\Users\Moussa\Desktop\documentation_ai
Using: PostgreSQL
Found X files to index
Creating index with Y document chunks
Indexing completed successfully!
Total files: X
Processed files: X
Total chunks: Y
```

### 6. Start the Server

```bash
python src/manage.py runserver
```

**Verify:**
- [ ] Server starts without errors
- [ ] Visit http://localhost:8000/health/
- [ ] Should see `{"status": "healthy", ...}`

## ✅ Test the Chatbot

### Test 1: Create a session

```bash
curl -X POST http://localhost:8000/api/sessions/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Session"}'
```

**Expected:** JSON with session ID

### Test 2: Send a message

```bash
# Replace SESSION_ID with the ID from Test 1
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is this project about?",
    "session_id": "SESSION_ID"
  }'
```

**Expected:** JSON with `message`, `sources`, and `message_id`

### Test 3: Search codebase

```bash
curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "database", "top_k": 3}'
```

**Expected:** Array of search results with scores

### Test 4: Python client

```bash
python chatbot_client.py
```

**Expected:** Demo runs and shows conversation

## ✅ Troubleshooting Checks

### If imports fail:
```bash
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall
```

### If pgvector fails:
```bash
# Check PostgreSQL version (needs 12+)
psql --version

# Install pgvector (Ubuntu/Debian)
sudo apt install postgresql-12-pgvector

# Install pgvector (macOS)
brew install pgvector

# Install pgvector (Windows)
# Download from: https://github.com/pgvector/pgvector/releases
```

### If OpenAI API fails:
```bash
# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### If Redis connection fails:
```bash
# Test Redis
redis-cli ping
# Should return: PONG

# Or with Docker
docker-compose exec redis redis-cli ping
```

### If indexing is slow:
- Normal: 10-50 files/minute depending on size
- First run is slowest (creating embeddings)
- Check OpenAI API rate limits
- Reduce chunk size in config if needed

## ✅ Configuration Verification

### Check Django settings:

```python
python src/manage.py shell
```

```python
from django.conf import settings
print(settings.INSTALLED_APPS)  # Should include 'core', 'rest_framework', 'pgvector'
```

### Check OpenAI connection:

```python
import os
from core.llm_factory.factory import LLMFactory

# Should not raise error
llm = LLMFactory.get_langchain_llm(model="gpt-3.5-turbo")
embeddings = LLMFactory.get_langchain_embeddings()
print("✓ OpenAI connection OK")
```

### Check vector store:

```python
from core.llm_factory.providers import VectorStoreProvider

# PostgreSQL
pg_store = VectorStoreProvider.get_postgres_vector_store()
print("✓ PostgreSQL vector store OK")

# Redis
redis_store = VectorStoreProvider.get_redis_vector_store()
print("✓ Redis vector store OK")
```

## ✅ Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'llama_index'` | Run `pip install -r requirements.txt` |
| `pgvector extension not found` | Enable with `CREATE EXTENSION vector;` |
| `OpenAI API key not found` | Set `OPENAI_API_KEY` in `.env` |
| `Connection refused (Redis)` | Start Redis: `redis-server` or `docker-compose up -d redis` |
| `Connection refused (PostgreSQL)` | Start PostgreSQL or check connection details |
| `No index found` | Run `python src/manage.py index_codebase` |
| Slow indexing | Normal for first run; check OpenAI rate limits |
| Import errors in IDE | Install packages in correct Python environment |

## ✅ Next Steps

Once everything is working:

- [ ] Read [CHATBOT_README.md](CHATBOT_README.md) for full API docs
- [ ] Read [QUICKSTART.md](QUICKSTART.md) for usage examples
- [ ] Customize system prompt in `chat_service.py`
- [ ] Adjust chunking parameters in `llm_factory/factory.py`
- [ ] Add authentication to API endpoints
- [ ] Build a frontend UI
- [ ] Deploy to production

## ✅ Quick Reference

```bash
# Start server
python src/manage.py runserver

# Index codebase
python src/manage.py index_codebase

# Enable pgvector
python src/manage.py setup_pgvector

# Run migrations
python src/manage.py migrate

# Test chatbot
python chatbot_client.py

# Check health
curl http://localhost:8000/health/
```

## ✅ Success Criteria

You're all set when:

- ✅ Server starts without errors
- ✅ Health check returns `{"status": "healthy"}`
- ✅ Indexing completes successfully
- ✅ Chat API returns intelligent responses
- ✅ Sources are included in responses
- ✅ Search returns relevant results

---

**Need help?** Check the troubleshooting section or review the logs for specific error messages.

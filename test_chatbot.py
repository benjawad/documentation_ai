"""
Test script for chatbot functionality
Run with: python src/manage.py shell < test_chatbot.py
"""
from core.services.chat_service import ChatbotService
from core.services.indexing_service import CodebaseIndexer
from core.models import ChatSession, IndexingJob
import os

print("=" * 60)
print("CHATBOT TEST SCRIPT")
print("=" * 60)

# Test 1: Check if OpenAI API key is set
print("\n1. Checking OpenAI API key...")
openai_key = os.getenv('OPENAI_API_KEY')
if openai_key and openai_key != 'sk-placeholder':
    print("✓ OpenAI API key is configured")
else:
    print("✗ OpenAI API key not configured. Please set OPENAI_API_KEY in .env")

# Test 2: Create a chat session
print("\n2. Creating chat session...")
try:
    session = ChatbotService.create_session(title="Test Session")
    print(f"✓ Session created: {session.id}")
except Exception as e:
    print(f"✗ Failed to create session: {str(e)}")

# Test 3: List sessions
print("\n3. Listing sessions...")
try:
    sessions = ChatbotService.list_sessions()
    print(f"✓ Found {len(sessions)} session(s)")
except Exception as e:
    print(f"✗ Failed to list sessions: {str(e)}")

# Test 4: Initialize indexer
print("\n4. Initializing indexer...")
try:
    indexer = CodebaseIndexer(use_postgres=True)
    print("✓ Indexer initialized with PostgreSQL")
except Exception as e:
    print(f"✗ Failed to initialize indexer: {str(e)}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
print("\nNext steps:")
print("1. Set OPENAI_API_KEY in your .env file")
print("2. Run migrations: python src/manage.py migrate")
print("3. Enable pgvector: CREATE EXTENSION IF NOT EXISTS vector;")
print("4. Index codebase: python src/manage.py index_codebase")
print("5. Start chatting via API!")

"""
Tests for the chatbot functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status
import uuid


class ChatSessionAPITests(TestCase):
    """Tests for chat session endpoints"""
    
    def setUp(self):
        self.client = APIClient()
    
    def test_create_session(self):
        """Test creating a new chat session"""
        response = self.client.post('/api/sessions/', {'title': 'Test Session'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['title'], 'Test Session')
    
    def test_list_sessions(self):
        """Test listing all sessions"""
        # Create a session first
        self.client.post('/api/sessions/', {'title': 'Session 1'}, format='json')
        self.client.post('/api/sessions/', {'title': 'Session 2'}, format='json')
        
        response = self.client.get('/api/sessions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 2)


class ChatAPITests(TestCase):
    """Tests for chat message endpoints"""
    
    def setUp(self):
        self.client = APIClient()
    
    @patch('core.views.ChatbotService')
    def test_chat_creates_session_if_not_provided(self, mock_service):
        """Test that chat creates a new session if none provided"""
        mock_session = Mock()
        mock_session.id = uuid.uuid4()
        mock_service.create_session.return_value = mock_session
        
        mock_instance = Mock()
        mock_instance.chat.return_value = {
            'message': 'Test response',
            'sources': [],
            'message_id': str(uuid.uuid4())
        }
        mock_service.return_value = mock_instance
        
        response = self.client.post('/api/chat/', {
            'message': 'Hello'
        }, format='json')
        
        # Session should be created
        mock_service.create_session.assert_called_once()
    
    @patch('core.views.ChatbotService')
    def test_chat_with_existing_session(self, mock_service):
        """Test chat with existing session"""
        session_id = str(uuid.uuid4())
        
        mock_instance = Mock()
        mock_instance.chat.return_value = {
            'message': 'Test response',
            'sources': [{'file_path': '/test.py', 'file_name': 'test.py'}],
            'message_id': str(uuid.uuid4())
        }
        mock_service.return_value = mock_instance
        
        response = self.client.post('/api/chat/', {
            'message': 'How does authentication work?',
            'session_id': session_id
        }, format='json')
        
        mock_service.assert_called_with(session_id=session_id)


class IndexingAPITests(TestCase):
    """Tests for indexing endpoints"""
    
    def setUp(self):
        self.client = APIClient()
    
    @patch('core.views.CodebaseIndexer')
    def test_start_indexing(self, mock_indexer):
        """Test starting indexing process"""
        mock_instance = Mock()
        mock_instance.index_codebase.return_value = {
            'status': 'success',
            'total_files': 10,
            'processed_files': 10,
            'total_chunks': 50
        }
        mock_indexer.return_value = mock_instance
        
        response = self.client.post('/api/index/', {
            'use_postgres': True
        }, format='json')
        
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_202_ACCEPTED])
        self.assertIn('job', response.data)
    
    @patch('core.tasks.index_codebase_task.delay')
    def test_async_indexing(self, mock_task):
        """Test async indexing with Celery"""
        response = self.client.post('/api/index/', {
            'async': True,
            'use_postgres': True
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('message', response.data)
        mock_task.assert_called_once()
    
    def test_get_indexing_jobs(self):
        """Test getting list of indexing jobs"""
        response = self.client.get('/api/index/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class SearchAPITests(TestCase):
    """Tests for search endpoints"""
    
    def setUp(self):
        self.client = APIClient()
    
    @patch('core.views.CodebaseIndexer')
    def test_search_documents(self, mock_indexer):
        """Test searching indexed documents"""
        mock_instance = Mock()
        mock_instance.search_similar_documents.return_value = [
            {
                'text': 'def authenticate(user):',
                'metadata': {'file_path': '/auth.py', 'file_name': 'auth.py'},
                'score': 0.95
            }
        ]
        mock_indexer.return_value = mock_instance
        
        response = self.client.post('/api/search/', {
            'query': 'authentication',
            'top_k': 5
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
    
    def test_search_requires_query(self):
        """Test that search requires a query parameter"""
        response = self.client.post('/api/search/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LLMFactoryTests(TestCase):
    """Tests for LLM Factory"""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_langchain_llm_creation(self):
        """Test creating LangChain LLM"""
        from core.llm_factory.factory import LLMFactory
        
        llm = LLMFactory.get_langchain_llm(model='gpt-3.5-turbo')
        self.assertIsNotNone(llm)
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_embeddings_creation(self):
        """Test creating embeddings"""
        from core.llm_factory.factory import LLMFactory
        
        embeddings = LLMFactory.get_langchain_embeddings()
        self.assertIsNotNone(embeddings)
    
    def test_missing_api_key_raises_error(self):
        """Test that missing API key raises error"""
        from core.llm_factory.factory import LLMFactory
        import os
        
        # Remove key if exists
        original_key = os.environ.pop('OPENAI_API_KEY', None)
        
        try:
            with self.assertRaises(ValueError):
                LLMFactory.get_langchain_llm()
        finally:
            # Restore key
            if original_key:
                os.environ['OPENAI_API_KEY'] = original_key


class ChatbotServiceTests(TestCase):
    """Tests for ChatbotService"""
    
    def test_create_session(self):
        """Test creating chat session"""
        from core.services.chat_service import ChatbotService
        
        session = ChatbotService.create_session(title='Test Session')
        self.assertIsNotNone(session.id)
        self.assertEqual(session.title, 'Test Session')
    
    def test_list_sessions(self):
        """Test listing sessions"""
        from core.services.chat_service import ChatbotService
        
        ChatbotService.create_session(title='Session 1')
        ChatbotService.create_session(title='Session 2')
        
        sessions = ChatbotService.list_sessions()
        self.assertGreaterEqual(len(sessions), 2)


class ModelTests(TestCase):
    """Tests for Django models"""
    
    def test_chat_session_creation(self):
        """Test ChatSession model"""
        from core.models import ChatSession
        
        session = ChatSession.objects.create(title='Test')
        self.assertIsNotNone(session.id)
        self.assertIsNotNone(session.created_at)
    
    def test_chat_message_creation(self):
        """Test ChatMessage model"""
        from core.models import ChatSession, ChatMessage
        
        session = ChatSession.objects.create(title='Test')
        message = ChatMessage.objects.create(
            session=session,
            role='user',
            content='Hello'
        )
        
        self.assertEqual(message.role, 'user')
        self.assertEqual(message.content, 'Hello')
        self.assertEqual(message.session, session)
    
    def test_indexing_job_creation(self):
        """Test IndexingJob model"""
        from core.models import IndexingJob
        
        job = IndexingJob.objects.create(status='pending')
        self.assertEqual(job.status, 'pending')
        self.assertEqual(job.total_files, 0)

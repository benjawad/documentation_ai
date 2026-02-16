from django.http import JsonResponse
from django.db import connection
from django.conf import settings
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.views import APIView
import redis
import uuid
import os

from core.models import ChatSession, ChatMessage, IndexingJob
from core.serializers import (
    ChatSessionSerializer, ChatSessionDetailSerializer,
    ChatMessageSerializer, ChatRequestSerializer, ChatResponseSerializer,
    IndexingJobSerializer, IndexingRequestSerializer,
    SearchRequestSerializer, SearchResultSerializer
)
from core.services.chat_service import ChatbotService
from core.services.indexing_service import CodebaseIndexer


def health_check(request):
    """
    Health check endpoint for monitoring and load balancers.
    Returns 200 OK if all services are healthy.
    """
    health_status = {
        'status': 'healthy',
        'services': {}
    }
    status_code = 200

    # Check Database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status['services']['database'] = 'healthy'
    except Exception as e:
        health_status['services']['database'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
        status_code = 503

    # Check Redis
    try:
        broker_url = settings.CELERY_BROKER_URL
        # Parse Redis URL
        if broker_url.startswith('redis://'):
            # Extract password if present
            if '@' in broker_url:
                auth_part = broker_url.split('//')[1].split('@')[0]
                if ':' in auth_part:
                    password = auth_part.split(':')[1]
                else:
                    password = None
                host_part = broker_url.split('@')[1].split('/')[0].split(':')[0]
                port = int(broker_url.split('@')[1].split('/')[0].split(':')[1]) if ':' in broker_url.split('@')[1].split('/')[0] else 6379
            else:
                password = None
                host_part = broker_url.split('//')[1].split('/')[0].split(':')[0]
                port = int(broker_url.split('//')[1].split('/')[0].split(':')[1]) if ':' in broker_url.split('//')[1].split('/')[0] else 6379
            
            r = redis.Redis(host=host_part, port=port, password=password, socket_connect_timeout=5)
            r.ping()
            health_status['services']['redis'] = 'healthy'
    except Exception as e:
        health_status['services']['redis'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
        status_code = 503

    return JsonResponse(health_status, status=status_code)


class ChatSessionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing chat sessions"""
    queryset = ChatSession.objects.all()
    serializer_class = ChatSessionSerializer
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ChatSessionDetailSerializer
        return ChatSessionSerializer
    
    def list(self, request):
        """List all chat sessions"""
        sessions = ChatbotService.list_sessions()
        return Response(sessions)
    
    def create(self, request):
        """Create a new chat session"""
        title = request.data.get('title', '')
        session = ChatbotService.create_session(title=title)
        serializer = self.get_serializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['delete'])
    def clear_history(self, request, pk=None):
        """Clear chat history for a session"""
        try:
            chatbot = ChatbotService(session_id=pk)
            chatbot.clear_history()
            return Response({'message': 'Chat history cleared'})
        except ChatSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )


@method_decorator(csrf_exempt, name='dispatch')
class ChatView(APIView):
    """View for handling chat messages"""
    
    def post(self, request):
        """Send a message and get a response"""
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        message = serializer.validated_data['message']
        session_id = serializer.validated_data.get('session_id')
        
        # Create new session if not provided
        if not session_id:
            session = ChatbotService.create_session()
            session_id = str(session.id)
        
        try:
            # Get response from chatbot
            chatbot = ChatbotService(session_id=session_id)
            response = chatbot.chat(message)
            response['session_id'] = session_id
            
            response_serializer = ChatResponseSerializer(data=response)
            response_serializer.is_valid(raise_exception=True)
            
            return Response(response_serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


def chatbot_ui(request):
    """Serve the chatbot UI interface"""
    return render(request, 'chatbot.html')


@method_decorator(csrf_exempt, name='dispatch')
class IndexingView(APIView):
    """View for handling codebase indexing"""
    
    def post(self, request):
        """Start indexing the codebase"""
        serializer = IndexingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        root_path = serializer.validated_data.get('root_path')
        use_postgres = serializer.validated_data.get('use_postgres', True)
        async_mode = request.data.get('async', False)
        
        # Use default path if not provided
        if not root_path:
            root_path = os.path.join(settings.BASE_DIR, '..')
        
        # Create indexing job
        job = IndexingJob.objects.create(status='pending')
        
        if async_mode:
            # Use Celery for async indexing
            from core.tasks import index_codebase_task
            index_codebase_task.delay(
                root_path=root_path,
                use_postgres=use_postgres,
                job_id=str(job.id)
            )
            
            job_serializer = IndexingJobSerializer(job)
            return Response({
                'job': job_serializer.data,
                'message': 'Indexing started in background'
            }, status=status.HTTP_202_ACCEPTED)
        
        try:
            # Start indexing synchronously
            indexer = CodebaseIndexer(use_postgres=use_postgres)
            result = indexer.index_codebase(root_path, job_id=str(job.id))
            
            job.refresh_from_db()
            job_serializer = IndexingJobSerializer(job)
            return Response({
                'job': job_serializer.data,
                'result': result
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            job.status = 'failed'
            job.error_message = str(e)
            job.save()
            
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get(self, request):
        """Get indexing job status"""
        job_id = request.query_params.get('job_id')
        
        if job_id:
            try:
                job = IndexingJob.objects.get(id=job_id)
                serializer = IndexingJobSerializer(job)
                return Response(serializer.data)
            except IndexingJob.DoesNotExist:
                return Response(
                    {'error': 'Job not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # List all jobs
            jobs = IndexingJob.objects.all()[:10]
            serializer = IndexingJobSerializer(jobs, many=True)
            return Response(serializer.data)


class SearchView(APIView):
    """View for searching indexed documents"""
    
    def post(self, request):
        """Search for similar documents"""
        serializer = SearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        query = serializer.validated_data['query']
        top_k = serializer.validated_data['top_k']
        
        try:
            indexer = CodebaseIndexer(use_postgres=True)
            results = indexer.search_similar_documents(query, top_k=top_k)
            
            result_serializer = SearchResultSerializer(results, many=True)
            return Response(result_serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


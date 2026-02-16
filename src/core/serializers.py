"""
Serializers for chat and indexing APIs
"""
from rest_framework import serializers
from core.models import ChatSession, ChatMessage, IndexingJob


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages"""
    
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'sources', 'created_at']
        read_only_fields = ['id', 'created_at']


class ChatSessionSerializer(serializers.ModelSerializer):
    """Serializer for chat sessions"""
    message_count = serializers.IntegerField(read_only=True)
    last_message = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'created_at', 'updated_at', 'message_count', 'last_message']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return {
                'content': last_msg.content[:100] + '...' if len(last_msg.content) > 100 else last_msg.content,
                'role': last_msg.role,
                'created_at': last_msg.created_at,
            }
        return None


class ChatSessionDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for chat sessions with messages"""
    messages = ChatMessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'created_at', 'updated_at', 'messages']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChatRequestSerializer(serializers.Serializer):
    """Serializer for chat requests"""
    message = serializers.CharField(required=True)
    session_id = serializers.UUIDField(required=False, allow_null=True)


class ChatResponseSerializer(serializers.Serializer):
    """Serializer for chat responses"""
    session_id = serializers.UUIDField()
    message = serializers.CharField()
    sources = serializers.ListField(child=serializers.DictField())
    message_id = serializers.UUIDField()


class IndexingJobSerializer(serializers.ModelSerializer):
    """Serializer for indexing jobs"""
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = IndexingJob
        fields = [
            'id', 'status', 'total_files', 'processed_files',
            'progress_percentage', 'error_message', 'metadata',
            'started_at', 'completed_at', 'created_at'
        ]
        read_only_fields = [
            'id', 'status', 'total_files', 'processed_files',
            'error_message', 'metadata', 'started_at', 'completed_at', 'created_at'
        ]
    
    def get_progress_percentage(self, obj):
        if obj.total_files > 0:
            return round((obj.processed_files / obj.total_files) * 100, 2)
        return 0


class IndexingRequestSerializer(serializers.Serializer):
    """Serializer for indexing requests"""
    root_path = serializers.CharField(required=False)
    use_postgres = serializers.BooleanField(default=True)


class SearchRequestSerializer(serializers.Serializer):
    """Serializer for document search requests"""
    query = serializers.CharField(required=True)
    top_k = serializers.IntegerField(default=5, min_value=1, max_value=20)


class SearchResultSerializer(serializers.Serializer):
    """Serializer for search results"""
    text = serializers.CharField()
    metadata = serializers.DictField()
    score = serializers.FloatField()

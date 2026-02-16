from django.db import models
from django.contrib.postgres.fields import ArrayField
from pgvector.django import VectorField
import uuid


class Document(models.Model):
    """Store indexed documents from the codebase"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file_path = models.CharField(max_length=500, unique=True)
    content = models.TextField()
    metadata = models.JSONField(default=dict)
    embedding = VectorField(dimensions=1536, null=True, blank=True)  # OpenAI embeddings
    chunk_index = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'documents'
        indexes = [
            models.Index(fields=['file_path']),
            models.Index(fields=['created_at']),
        ]
        
    def __str__(self):
        return f"{self.file_path} (chunk {self.chunk_index})"


class ChatSession(models.Model):
    """Store chat sessions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'chat_sessions'
        ordering = ['-updated_at']
        
    def __str__(self):
        return f"Session {self.id} - {self.title or 'Untitled'}"


class ChatMessage(models.Model):
    """Store individual chat messages"""
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)  # Referenced documents
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
        ]
        
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."


class IndexingJob(models.Model):
    """Track indexing jobs"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_files = models.IntegerField(default=0)
    processed_files = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'indexing_jobs'
        ordering = ['-created_at']
        
    def __str__(self):
        return f"Indexing Job {self.id} - {self.status}"

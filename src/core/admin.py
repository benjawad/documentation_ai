from django.contrib import admin
from core.models import ChatSession, ChatMessage, Document, IndexingJob


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('title', 'id')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'role', 'created_at', 'message_preview')
    list_filter = ('role', 'created_at', 'session')
    search_fields = ('content', 'session__id')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)
    
    def message_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    message_preview.short_description = 'Message Preview'


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'file_path', 'content_preview', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('file_path', 'content')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    
    def content_preview(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    content_preview.short_description = 'Content Preview'


@admin.register(IndexingJob)
class IndexingJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'total_files', 'processed_files', 'progress', 'started_at', 'completed_at')
    list_filter = ('status', 'started_at', 'completed_at')
    search_fields = ('id', 'error_message')
    readonly_fields = ('id', 'started_at', 'completed_at')
    ordering = ('-started_at',)
    
    def progress(self, obj):
        if obj.total_files and obj.total_files > 0:
            percentage = (obj.processed_files / obj.total_files) * 100
            return f"{percentage:.1f}%"
        return "N/A"
    progress.short_description = 'Progress'

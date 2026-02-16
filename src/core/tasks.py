"""
Celery tasks for async operations
"""
from celery import shared_task
from django.conf import settings
import logging
import os

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def index_codebase_task(self, root_path: str = None, use_postgres: bool = True, job_id: str = None):
    """
    Async task to index the codebase
    
    Args:
        root_path: Root path to index
        use_postgres: Use PostgreSQL (True) or Redis (False)
        job_id: Optional job ID for tracking
        
    Returns:
        Dictionary with indexing results
    """
    from core.services.indexing_service import CodebaseIndexer
    from core.models import IndexingJob
    
    logger.info(f"Starting async indexing task. Job ID: {job_id}")
    
    if not root_path:
        root_path = os.path.join(settings.BASE_DIR, '..')
    
    try:
        indexer = CodebaseIndexer(use_postgres=use_postgres)
        result = indexer.index_codebase(root_path, job_id=job_id)
        
        logger.info(f"Indexing completed. Files: {result['total_files']}, Chunks: {result['total_chunks']}")
        return result
        
    except Exception as e:
        logger.error(f"Indexing failed: {str(e)}")
        
        # Update job status if job_id provided
        if job_id:
            try:
                job = IndexingJob.objects.get(id=job_id)
                job.status = 'failed'
                job.error_message = str(e)
                job.save()
            except:
                pass
        
        # Retry on failure
        raise self.retry(exc=e, countdown=60)


@shared_task
def cleanup_old_jobs_task():
    """
    Clean up old indexing jobs (older than 7 days)
    """
    from core.models import IndexingJob
    from datetime import datetime, timedelta
    
    cutoff = datetime.now() - timedelta(days=7)
    deleted_count, _ = IndexingJob.objects.filter(
        created_at__lt=cutoff,
        status__in=['completed', 'failed']
    ).delete()
    
    logger.info(f"Cleaned up {deleted_count} old indexing jobs")
    return deleted_count


@shared_task
def reindex_changed_files_task(file_paths: list, use_postgres: bool = True):
    """
    Re-index specific files that have changed
    
    Args:
        file_paths: List of file paths to re-index
        use_postgres: Use PostgreSQL or Redis
        
    Returns:
        Number of files re-indexed
    """
    from core.services.indexing_service import CodebaseIndexer
    from llama_index.core import Document as LlamaDocument
    
    logger.info(f"Re-indexing {len(file_paths)} files")
    
    try:
        indexer = CodebaseIndexer(use_postgres=use_postgres)
        
        documents = []
        for file_path in file_paths:
            docs = indexer._process_file(file_path)
            documents.extend(docs)
        
        if documents:
            index = indexer.get_index()
            index.insert_nodes(indexer.node_parser.get_nodes_from_documents(documents))
        
        logger.info(f"Re-indexed {len(file_paths)} files with {len(documents)} chunks")
        return len(file_paths)
        
    except Exception as e:
        logger.error(f"Re-indexing failed: {str(e)}")
        raise

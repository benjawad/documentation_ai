"""
Management command to initialize and index the codebase
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import os

from core.services.indexing_service import CodebaseIndexer
from core.models import IndexingJob


class Command(BaseCommand):
    help = 'Index the codebase for the chatbot'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            type=str,
            default=None,
            help='Root path to index (defaults to project root)',
        )
        parser.add_argument(
            '--use-redis',
            action='store_true',
            help='Use Redis instead of PostgreSQL for vector storage',
        )

    def handle(self, *args, **options):
        root_path = options['path']
        use_postgres = not options['use_redis']
        
        if not root_path:
            root_path = os.path.join(settings.BASE_DIR, '..')
        
        self.stdout.write(f"Indexing codebase from: {root_path}")
        self.stdout.write(f"Using: {'PostgreSQL' if use_postgres else 'Redis'}")
        
        # Create indexing job
        job = IndexingJob.objects.create(status='pending')
        
        try:
            # Initialize indexer
            indexer = CodebaseIndexer(use_postgres=use_postgres)
            
            # Index codebase
            result = indexer.index_codebase(root_path, job_id=str(job.id))
            
            self.stdout.write(self.style.SUCCESS(
                f"Indexing completed successfully!"
            ))
            self.stdout.write(f"Total files: {result['total_files']}")
            self.stdout.write(f"Processed files: {result['processed_files']}")
            self.stdout.write(f"Total chunks: {result['total_chunks']}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"Indexing failed: {str(e)}"
            ))
            raise

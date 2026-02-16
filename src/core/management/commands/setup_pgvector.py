"""
Management command to setup pgvector extension
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Enable pgvector extension in PostgreSQL'

    def handle(self, *args, **options):
        self.stdout.write("Enabling pgvector extension...")
        
        try:
            with connection.cursor() as cursor:
                # Enable pgvector extension
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                
                # Verify it's enabled
                cursor.execute(
                    "SELECT extname FROM pg_extension WHERE extname = 'vector';"
                )
                result = cursor.fetchone()
                
                if result:
                    self.stdout.write(self.style.SUCCESS(
                        "✓ pgvector extension is enabled"
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        "✗ Failed to enable pgvector extension"
                    ))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"Error enabling pgvector: {str(e)}"
            ))
            self.stdout.write(
                "Make sure pgvector is installed on your PostgreSQL server."
            )
            raise

"""
Document indexing service using LlamaIndex
Indexes the codebase for RAG-based chatbot
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
from datetime import datetime
import time

from llama_index.core import VectorStoreIndex, StorageContext, Document as LlamaDocument
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.core.schema import TextNode

from core.llm_factory.factory import LLMFactory, LLMConfig
from core.llm_factory.providers import VectorStoreProvider, VectorStoreConfig
from core.services.files import FileSystemVisitor
from core.models import Document, IndexingJob

logger = logging.getLogger(__name__)


class CodebaseIndexer:
    """Service for indexing codebase using LlamaIndex"""
    
    def __init__(self, use_postgres: bool = True):
        """
        Initialize the indexer
        
        Args:
            use_postgres: If True, use PostgreSQL; otherwise use Redis
        """
        self.use_postgres = use_postgres
        
        # Configure LlamaIndex
        LLMFactory.configure_llama_index_settings(
            llm_model=LLMConfig.DEFAULT_LLM_MODEL,
            embed_model=LLMConfig.DEFAULT_EMBEDDING_MODEL,
            chunk_size=LLMConfig.DEFAULT_CHUNK_SIZE,
            chunk_overlap=LLMConfig.DEFAULT_CHUNK_OVERLAP,
        )
        
        # Get embeddings
        self.embed_model = LLMFactory.get_llama_index_embeddings()
        
        # Initialize vector store
        if use_postgres:
            self.vector_store = VectorStoreProvider.get_postgres_vector_store()
        else:
            self.vector_store = VectorStoreProvider.get_redis_vector_store()
        
        # Storage context
        self.storage_context = StorageContext.from_defaults(
            vector_store=self.vector_store
        )
        
        # Node parser
        self.node_parser = SimpleNodeParser.from_defaults(
            chunk_size=LLMConfig.DEFAULT_CHUNK_SIZE,
            chunk_overlap=LLMConfig.DEFAULT_CHUNK_OVERLAP,
        )
    
    def index_codebase(
        self,
        root_path: str,
        job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Index the entire codebase
        
        Args:
            root_path: Root path of the project
            job_id: Optional indexing job ID for tracking
            
        Returns:
            Dictionary with indexing results
        """
        logger.info(f"Starting codebase indexing from {root_path}")
        
        # Update job status
        if job_id:
            job = IndexingJob.objects.get(id=job_id)
            job.status = 'running'
            job.started_at = datetime.now()
            job.save()
        
        try:
            # Collect all files
            visitor = FileSystemVisitor()
            tree = visitor.visit(root_path)
            files = self._extract_files_from_tree(tree)
            
            total_files = len(files)
            logger.info(f"Found {total_files} files to index")
            
            if job_id:
                job.total_files = total_files
                job.save()
            
            # Process files
            # Collect all documents first
            documents = []
            processed_count = 0
            
            for file_path in files:
                try:
                    docs = self._process_file(file_path)
                    documents.extend(docs)
                    processed_count += 1
                    
                    if job_id and processed_count % 10 == 0:
                        job.processed_files = processed_count
                        job.save()
                        
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {str(e)}")
                    continue
            
            # Process documents in SMALL batches to respect rate limits (40k TPM limit)
            # Each chunk is ~512 tokens, so 5 docs = ~2500 tokens per batch (safe margin)
            logger.info(f"Creating index with {len(documents)} document chunks")
            batch_size = 5  # Small batches to stay under rate limits
            batches = [documents[i:i + batch_size] for i in range(0, len(documents), batch_size)]
            
            logger.info(f"Processing {len(batches)} batches of documents (batch_size={batch_size})")
            
            # Process first batch to create index
            if batches:
                logger.info(f"Processing batch 1/{len(batches)} ({len(batches[0])} documents)")
                index = VectorStoreIndex.from_documents(
                    batches[0],
                    storage_context=self.storage_context,
                    embed_model=self.embed_model,
                )
                
                # Add remaining batches with delays to respect rate limits
                for i, batch in enumerate(batches[1:], start=2):
                    logger.info(f"Processing batch {i}/{len(batches)} ({len(batch)} documents)")
                    
                    # Wait 2 seconds between batches to stay under 40k TPM
                    time.sleep(2)
                    
                    # Insert documents one at a time with small delay
                    for doc in batch:
                        try:
                            index.insert(doc)
                            time.sleep(0.3)  # Small delay between individual docs
                        except Exception as e:
                            if "429" in str(e) or "rate_limit" in str(e).lower():
                                logger.warning(f"Rate limited, waiting 60 seconds...")
                                time.sleep(60)
                                index.insert(doc)  # Retry
                            else:
                                raise
                    
                    # Update progress
                    if job_id:
                        progress = (i / len(batches)) * 100
                        job.metadata = {
                            'progress': f"{progress:.1f}%",
                            'batches_processed': i,
                            'total_batches': len(batches),
                        }
                        job.save()
            else:
                # No documents to index
                index = VectorStoreIndex.from_documents(
                    [],
                    storage_context=self.storage_context,
                    embed_model=self.embed_model,
                )
            
            # Update job
            if job_id:
                job.status = 'completed'
                job.processed_files = processed_count
                job.completed_at = datetime.now()
                job.metadata = {
                    'total_chunks': len(documents),
                    'total_files': total_files,
                    'batches_processed': len(batches),
                }
                job.save()
            
            return {
                'status': 'success',
                'total_files': total_files,
                'processed_files': processed_count,
                'total_chunks': len(documents),
                'batches': len(batches),
            }
            
        except Exception as e:
            logger.error(f"Indexing failed: {str(e)}")
            
            if job_id:
                job.status = 'failed'
                job.error_message = str(e)
                job.completed_at = datetime.now()
                job.save()
            
            raise
    
    def _extract_files_from_tree(self, tree: Dict) -> List[str]:
        """Extract file paths from file tree"""
        files = []
        
        def traverse(node):
            if node.get('type') == 'file':
                files.append(node['path'])
            elif node.get('type') == 'directory' and node.get('children'):
                for child in node['children']:
                    traverse(child)
        
        traverse(tree)
        return files
    
    def _process_file(self, file_path: str) -> List[LlamaDocument]:
        """
        Process a single file and create documents
        
        Args:
            file_path: Path to the file
            
        Returns:
            List of LlamaIndex documents
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {str(e)}")
            return []
        
        # Create metadata
        path_obj = Path(file_path)
        metadata = {
            'file_path': str(file_path),
            'file_name': path_obj.name,
            'file_type': path_obj.suffix,
            'file_size': len(content),
        }
        
        # Create document
        doc = LlamaDocument(
            text=content,
            metadata=metadata,
        )
        
        return [doc]
    
    def get_index(self) -> VectorStoreIndex:
        """
        Get or create the vector index
        
        Returns:
            VectorStoreIndex instance
        """
        try:
            # Try to load existing index
            index = VectorStoreIndex.from_vector_store(
                vector_store=self.vector_store,
                embed_model=self.embed_model,
            )
            return index
        except:
            # Create new empty index
            return VectorStoreIndex.from_documents(
                [],
                storage_context=self.storage_context,
                embed_model=self.embed_model,
            )
    
    def search_similar_documents(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of similar documents with metadata
        """
        index = self.get_index()
        retriever = index.as_retriever(similarity_top_k=top_k)
        
        nodes = retriever.retrieve(query)
        
        results = []
        for node in nodes:
            results.append({
                'text': node.get_content(),
                'metadata': node.metadata,
                'score': node.score,
            })
        
        return results

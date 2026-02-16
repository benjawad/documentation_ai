"""
Vector store providers for LangChain and LlamaIndex
"""
from typing import Optional, List, Any, Dict
import os
from pathlib import Path

from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.core.schema import Document as LlamaDocument
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.vector_stores.redis import RedisVectorStore

from langchain_community.vectorstores import Redis as LangChainRedis
from langchain_community.vectorstores.pgvector import PGVector

import redis


class VectorStoreProvider:
    """Provider for vector store instances"""
    
    @staticmethod
    def get_postgres_vector_store(
        table_name: str = "embeddings",
        embed_dim: int = 1536,
        schema_name: str = "public"
    ) -> PGVectorStore:
        """
        Create a LlamaIndex PostgreSQL vector store
        
        Args:
            table_name: Name of the table for vectors
            embed_dim: Dimension of embeddings (1536 for OpenAI)
            schema_name: PostgreSQL schema name
            
        Returns:
            PGVectorStore instance
        """
        # Get database connection details from environment
        db_host = os.getenv('DB_HOST', 'db')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'ai_analyst')
        db_user = os.getenv('DB_USER', 'postgres')
        db_password = os.getenv('DB_PASSWORD', 'password')
        
        # Use individual parameters instead of connection_string
        # to avoid port parsing issues in LlamaIndex
        return PGVectorStore.from_params(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
            table_name=table_name,
            embed_dim=embed_dim,
            schema_name=schema_name,
            perform_setup=True,
        )
    
    @staticmethod
    def get_redis_vector_store(
        index_name: str = "codebase_index",
        prefix: str = "doc"
    ) -> RedisVectorStore:
        """
        Create a LlamaIndex Redis vector store
        
        Args:
            index_name: Name of the Redis index
            prefix: Prefix for document keys
            
        Returns:
            RedisVectorStore instance
        """
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', '6379'))
        redis_password = os.getenv('REDIS_PASSWORD', '')
        
        return RedisVectorStore(
            redis_url=f"redis://:{redis_password}@{redis_host}:{redis_port}" if redis_password 
                     else f"redis://{redis_host}:{redis_port}",
            index_name=index_name,
            index_prefix=prefix,
        )
    
    @staticmethod
    def get_langchain_postgres_store(
        collection_name: str = "codebase",
        embeddings: Any = None
    ) -> PGVector:
        """
        Create a LangChain PostgreSQL vector store
        
        Args:
            collection_name: Name of the collection
            embeddings: Embeddings instance
            
        Returns:
            PGVector instance
        """
        if embeddings is None:
            from core.llm_factory.factory import LLMFactory
            embeddings = LLMFactory.get_langchain_embeddings()
        
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'postgres')
        db_user = os.getenv('DB_USER', 'postgres')
        db_password = os.getenv('DB_PASSWORD', 'postgres')
        
        connection_string = (
            f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        )
        
        return PGVector(
            connection_string=connection_string,
            collection_name=collection_name,
            embedding_function=embeddings,
        )
    
    @staticmethod
    def get_langchain_redis_store(
        index_name: str = "codebase",
        embeddings: Any = None
    ) -> LangChainRedis:
        """
        Create a LangChain Redis vector store
        
        Args:
            index_name: Name of the Redis index
            embeddings: Embeddings instance
            
        Returns:
            Redis instance
        """
        if embeddings is None:
            from core.llm_factory.factory import LLMFactory
            embeddings = LLMFactory.get_langchain_embeddings()
        
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', '6379'))
        redis_password = os.getenv('REDIS_PASSWORD', '')
        
        redis_url = (
            f"redis://:{redis_password}@{redis_host}:{redis_port}" if redis_password 
            else f"redis://{redis_host}:{redis_port}"
        )
        
        return LangChainRedis(
            redis_url=redis_url,
            index_name=index_name,
            embedding=embeddings,
        )


class VectorStoreConfig:
    """Configuration for vector stores"""
    
    # Default store type
    DEFAULT_STORE = "postgres"  # Options: "postgres", "redis"
    
    # PostgreSQL settings
    POSTGRES_TABLE_NAME = "llama_index_embeddings"
    POSTGRES_SCHEMA = "public"
    EMBEDDING_DIMENSION = 1536  # OpenAI default
    
    # Redis settings
    REDIS_INDEX_NAME = "codebase_index"
    REDIS_PREFIX = "doc"

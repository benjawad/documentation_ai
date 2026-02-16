"""
LLM Factory for creating LangChain and LlamaIndex providers
"""
from typing import Optional, Dict, Any
from django.conf import settings
import os

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from llama_index.core import Settings
from llama_index.llms.openai import OpenAI as LlamaOpenAI
from llama_index.embeddings.openai import OpenAIEmbedding


class LLMFactory:
    """Factory for creating LLM instances"""
    
    @staticmethod
    def get_langchain_llm(
        model: str = "gpt-4",
        temperature: float = 0.7,
        **kwargs
    ) -> ChatOpenAI:
        """
        Create a LangChain ChatOpenAI instance
        
        Args:
            model: Model name (e.g., 'gpt-4', 'gpt-3.5-turbo')
            temperature: Creativity level (0-1)
            **kwargs: Additional parameters
            
        Returns:
            ChatOpenAI instance
        """
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            openai_api_key=api_key,
            **kwargs
        )
    
    @staticmethod
    def get_langchain_embeddings(
        model: str = "text-embedding-3-small",
        **kwargs
    ) -> OpenAIEmbeddings:
        """
        Create a LangChain OpenAI embeddings instance
        
        Args:
            model: Embedding model name
            **kwargs: Additional parameters
            
        Returns:
            OpenAIEmbeddings instance
        """
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        return OpenAIEmbeddings(
            model=model,
            openai_api_key=api_key,
            **kwargs
        )
    
    @staticmethod
    def get_llama_index_llm(
        model: str = "gpt-4",
        temperature: float = 0.7,
        **kwargs
    ) -> LlamaOpenAI:
        """
        Create a LlamaIndex OpenAI LLM instance
        
        Args:
            model: Model name
            temperature: Creativity level (0-1)
            **kwargs: Additional parameters
            
        Returns:
            LlamaOpenAI instance
        """
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        return LlamaOpenAI(
            model=model,
            temperature=temperature,
            api_key=api_key,
            **kwargs
        )
    
    @staticmethod
    def get_llama_index_embeddings(
        model: str = "text-embedding-3-small",
        **kwargs
    ) -> OpenAIEmbedding:
        """
        Create a LlamaIndex OpenAI embeddings instance
        
        Args:
            model: Embedding model name
            **kwargs: Additional parameters
            
        Returns:
            OpenAIEmbedding instance
        """
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        return OpenAIEmbedding(
            model=model,
            api_key=api_key,
            **kwargs
        )
    
    @staticmethod
    def configure_llama_index_settings(
        llm_model: str = "gpt-4",
        embed_model: str = "text-embedding-3-small",
        chunk_size: int = 1024,
        chunk_overlap: int = 200,
    ):
        """
        Configure global LlamaIndex settings
        
        Args:
            llm_model: LLM model name
            embed_model: Embedding model name
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
        """
        Settings.llm = LLMFactory.get_llama_index_llm(model=llm_model)
        Settings.embed_model = LLMFactory.get_llama_index_embeddings(model=embed_model)
        Settings.chunk_size = chunk_size
        Settings.chunk_overlap = chunk_overlap


class LLMConfig:
    """Configuration constants for LLM services"""
    
    # Model configurations
    DEFAULT_LLM_MODEL = "gpt-4"
    DEFAULT_CHAT_MODEL = "gpt-3.5-turbo"
    DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
    
    # Generation parameters
    DEFAULT_TEMPERATURE = 0.7
    CREATIVE_TEMPERATURE = 0.9
    PRECISE_TEMPERATURE = 0.2
    
    # Chunking parameters - small chunks to stay under rate limits
    DEFAULT_CHUNK_SIZE = 256  # Small chunks to reduce token count per embedding
    DEFAULT_CHUNK_OVERLAP = 50  # Minimal overlap
    
    # Retrieval parameters
    DEFAULT_TOP_K = 5
    DEFAULT_SIMILARITY_THRESHOLD = 0.7

# Architecture Analysis Summary

## Overview
- **Total Classes**: 42
- **Inheritance Relationships**: 31
- **Dependency Relationships**: 89
- **Core Classes**: 42

## Core Classes (Most Connected)

### ChatbotService
- **Module**: `/app/core/services/chat_service.py`
- **Connections**: 10
- **Uses**: ChatMessageHistory, ChatSession, Dict[str, Any], List[Dict[str, Any]], _create_chain (+5 more)
- **Description**: Service for handling chatbot conversations with codebase context

### CodebaseIndexer
- **Module**: `/app/core/services/indexing_service.py`
- **Connections**: 8
- **Uses**: Dict[str, Any], List[Dict[str, Any]], List[str], LlamaDocument, VectorStoreIndex (+3 more)
- **Description**: Service for indexing codebase using LlamaIndex

### Document
- **Module**: `/app/core/models.py`
- **Connections**: 8
- **Inherits**: Model
- **Uses**: CharField, DateTimeField, IntegerField, JSONField, TextField (+2 more)
- **Description**: Store indexed documents from the codebase

### ChatMessage
- **Module**: `/app/core/models.py`
- **Connections**: 7
- **Inherits**: Model
- **Uses**: CharField, DateTimeField, ForeignKey, JSONField, TextField (+1 more)
- **Description**: Store individual chat messages

### IndexingJob
- **Module**: `/app/core/models.py`
- **Connections**: 7
- **Inherits**: Model
- **Uses**: CharField, DateTimeField, IntegerField, JSONField, TextField (+1 more)
- **Description**: Track indexing jobs

### RelationshipExtractor
- **Module**: `/app/core/services/relationship_service.py`
- **Connections**: 5
- **Uses**: ClassRelationship, Dict[str, Dict], List[str], Optional[str], Set[str]
- **Description**: Extracts relationships from your project JSON.
Works directly with the output of ProjectAnalyzer.

### ChatSession
- **Module**: `/app/core/models.py`
- **Connections**: 5
- **Inherits**: Model
- **Uses**: CharField, DateTimeField, JSONField, UUIDField
- **Description**: Store chat sessions

### LLMFactory
- **Module**: `/app/core/llm_factory/factory.py`
- **Connections**: 4
- **Uses**: ChatOpenAI, LlamaOpenAI, OpenAIEmbedding, OpenAIEmbeddings
- **Description**: Factory for creating LLM instances

### VectorStoreProvider
- **Module**: `/app/core/llm_factory/providers.py`
- **Connections**: 4
- **Uses**: LangChainRedis, PGVector, PGVectorStore, RedisVectorStore
- **Description**: Provider for vector store instances

### ClassRelationship
- **Module**: `/app/core/services/relationship_service.py`
- **Connections**: 4
- **Uses**: List[Dict], List[str], Optional[str], Set[str]
- **Description**: Represents relationships for a single class


## Diagrams

- [Class Diagram](class_diagram.mmd) - Paste into [Mermaid Live](https://mermaid.live)
- [Relationships JSON](class_relationships.json) - Full data export
- [Full Project Context](full_project_context.json) - Complete tree with AST analysis

## How to View

### Mermaid Diagram
1. Copy content from `class_diagram.mmd`
2. Go to https://mermaid.live
3. Paste and view

### JSON Data
- Use `class_relationships.json` for programmatic access
- Feed to LLM for architecture analysis
- Use for dependency tracking

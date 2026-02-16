"""
Chat service using LangChain for conversational AI with RAG
"""
from typing import List, Dict, Any, Optional
import logging
import uuid

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_message_histories import ChatMessageHistory

from core.llm_factory.factory import LLMFactory, LLMConfig
from core.llm_factory.providers import VectorStoreProvider
from core.models import ChatSession, ChatMessage

logger = logging.getLogger(__name__)


class ChatbotService:
    """Service for handling chatbot conversations with codebase context"""
    
    SYSTEM_PROMPT = """You are an expert AI assistant specialized in helping developers understand their codebase.
You have access to the indexed codebase and can answer questions about:
- Code structure and architecture
- Specific functions, classes, and their implementations
- How different parts of the code interact
- Best practices and suggestions for improvements
- Debugging and troubleshooting

When answering:
1. Be precise and reference specific files and line numbers when possible
2. Provide code examples when relevant
3. Explain complex concepts clearly
4. If you're not sure about something, say so
5. Use the context from the codebase to give accurate answers"""
    
    def __init__(self, session_id: str, use_postgres: bool = True):
        """
        Initialize the chatbot service
        
        Args:
            session_id: UUID of the chat session (can be string or UUID)
            use_postgres: If True, use PostgreSQL; otherwise use Redis
        """
        # Convert string UUID to UUID object if needed
        if isinstance(session_id, str):
            try:
                session_id = uuid.UUID(session_id)
            except ValueError:
                raise ValueError(f"Invalid UUID format: {session_id}")
        
        self.session_id = session_id
        self.use_postgres = use_postgres
        
        # Get or create session
        self.session, created = ChatSession.objects.get_or_create(id=session_id)
        
        # Initialize LLM
        self.llm = LLMFactory.get_langchain_llm(
            model=LLMConfig.DEFAULT_CHAT_MODEL,
            temperature=LLMConfig.DEFAULT_TEMPERATURE,
        )
        
        # Initialize embeddings
        self.embeddings = LLMFactory.get_langchain_embeddings()
        
        # Initialize vector store
        if use_postgres:
            self.vector_store = VectorStoreProvider.get_langchain_postgres_store(
                embeddings=self.embeddings
            )
        else:
            self.vector_store = VectorStoreProvider.get_langchain_redis_store(
                embeddings=self.embeddings
            )
        
        # Create retriever
        self.retriever = self.vector_store.as_retriever(
            search_kwargs={"k": LLMConfig.DEFAULT_TOP_K}
        )
        
        # Initialize chat history
        self.chat_history = ChatMessageHistory()
        
        # Load existing chat history
        self._load_chat_history()
        
        # Create the RAG chain
        self.chain = self._create_chain()
    
    def _create_chain(self):
        """Create a simple RAG chain using LCEL"""
        
        # Define the prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT + "\n\nUse the following context to answer the question:\n\n{context}"),
            ("human", "{question}"),
        ])
        
        def format_docs(docs):
            """Format documents for context"""
            return "\n\n".join(doc.page_content for doc in docs)
        
        # Create RAG chain using LCEL
        rag_chain = (
            {"context": self.retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )
        
        return rag_chain
    
    def _load_chat_history(self):
        """Load existing chat history from database into chat history"""
        messages = ChatMessage.objects.filter(
            session=self.session
        ).order_by('created_at')
        
        for msg in messages:
            if msg.role == 'user':
                self.chat_history.add_user_message(msg.content)
            elif msg.role == 'assistant':
                self.chat_history.add_ai_message(msg.content)
    
    def chat(self, message: str) -> Dict[str, Any]:
        """
        Send a message and get a response
        
        Args:
            message: User message
            
        Returns:
            Dictionary with response and sources
        """
        logger.info(f"Processing message for session {self.session_id}")
        
        # Save user message
        user_msg = ChatMessage.objects.create(
            session=self.session,
            role='user',
            content=message
        )
        
        try:
            # Get response from chain
            answer = self.chain.invoke(message)
            
            # Get source documents directly from retriever for metadata
            source_docs = self.retriever.invoke(message)
            
            # Extract source information
            sources = []
            for doc in source_docs:
                sources.append({
                    'file_path': doc.metadata.get('file_path', ''),
                    'file_name': doc.metadata.get('file_name', ''),
                    'content_preview': doc.page_content[:200] + '...' if len(doc.page_content) > 200 else doc.page_content,
                })
            
            # Add messages to chat history
            self.chat_history.add_user_message(message)
            self.chat_history.add_ai_message(answer)
            
            # Save assistant message
            assistant_msg = ChatMessage.objects.create(
                session=self.session,
                role='assistant',
                content=answer,
                sources=sources
            )
            
            # Update session timestamp
            self.session.save()
            
            return {
                'message': answer,
                'sources': sources,
                'message_id': str(assistant_msg.id),
            }
            
        except Exception as e:
            logger.error(f"Error processing chat message: {str(e)}")
            raise
    
    def get_history(self) -> List[Dict[str, Any]]:
        """
        Get chat history for the session
        
        Returns:
            List of messages
        """
        messages = ChatMessage.objects.filter(
            session=self.session
        ).order_by('created_at')
        
        return [
            {
                'id': str(msg.id),
                'role': msg.role,
                'content': msg.content,
                'sources': msg.sources,
                'created_at': msg.created_at.isoformat(),
            }
            for msg in messages
        ]
    
    def clear_history(self):
        """Clear chat history"""
        ChatMessage.objects.filter(session=self.session).delete()
        self.memory.clear()
    
    @staticmethod
    def create_session(title: str = "") -> ChatSession:
        """
        Create a new chat session
        
        Args:
            title: Optional session title
            
        Returns:
            ChatSession instance
        """
        return ChatSession.objects.create(title=title)
    
    @staticmethod
    def list_sessions() -> List[Dict[str, Any]]:
        """
        List all chat sessions
        
        Returns:
            List of session dictionaries
        """
        sessions = ChatSession.objects.all()
        
        return [
            {
                'id': str(session.id),
                'title': session.title,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
                'message_count': session.messages.count(),
            }
            for session in sessions
        ]
"""
Example client for the AI Chatbot API
Demonstrates how to interact with the chatbot programmatically
"""
import requests
import json
from typing import Optional
import time


class ChatbotClient:
    """Client for interacting with the AI Chatbot API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session_id: Optional[str] = None
    
    def create_session(self, title: str = "") -> dict:
        """Create a new chat session"""
        response = requests.post(
            f"{self.base_url}/api/sessions/",
            json={"title": title}
        )
        response.raise_for_status()
        session = response.json()
        self.session_id = session['id']
        print(f"Created session: {self.session_id}")
        return session
    
    def list_sessions(self) -> list:
        """List all chat sessions"""
        response = requests.get(f"{self.base_url}/api/sessions/")
        response.raise_for_status()
        return response.json()
    
    def get_session(self, session_id: str) -> dict:
        """Get session details with messages"""
        response = requests.get(f"{self.base_url}/api/sessions/{session_id}/")
        response.raise_for_status()
        return response.json()
    
    def chat(self, message: str, session_id: Optional[str] = None) -> dict:
        """Send a message to the chatbot"""
        if session_id is None:
            session_id = self.session_id
        
        if session_id is None:
            raise ValueError("No session ID provided. Create a session first.")
        
        response = requests.post(
            f"{self.base_url}/api/chat/",
            json={
                "message": message,
                "session_id": session_id
            }
        )
        response.raise_for_status()
        return response.json()
    
    def search(self, query: str, top_k: int = 5) -> list:
        """Search the codebase"""
        response = requests.post(
            f"{self.base_url}/api/search/",
            json={
                "query": query,
                "top_k": top_k
            }
        )
        response.raise_for_status()
        return response.json()
    
    def start_indexing(self, root_path: Optional[str] = None, use_postgres: bool = True) -> dict:
        """Start indexing the codebase"""
        data = {"use_postgres": use_postgres}
        if root_path:
            data["root_path"] = root_path
        
        response = requests.post(
            f"{self.base_url}/api/index/",
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def get_indexing_status(self, job_id: str) -> dict:
        """Get status of an indexing job"""
        response = requests.get(
            f"{self.base_url}/api/index/",
            params={"job_id": job_id}
        )
        response.raise_for_status()
        return response.json()
    
    def clear_history(self, session_id: Optional[str] = None) -> dict:
        """Clear chat history for a session"""
        if session_id is None:
            session_id = self.session_id
        
        if session_id is None:
            raise ValueError("No session ID provided")
        
        response = requests.delete(
            f"{self.base_url}/api/sessions/{session_id}/clear_history/"
        )
        response.raise_for_status()
        return response.json()


def demo():
    """Demonstration of the chatbot client"""
    print("=" * 70)
    print("AI CHATBOT CLIENT DEMO")
    print("=" * 70)
    
    # Initialize client
    client = ChatbotClient()
    
    # Create a new session
    print("\n1. Creating new chat session...")
    session = client.create_session(title="Demo Session")
    print(f"   Session ID: {session['id']}")
    
    # Ask some questions
    questions = [
        "What is this project about?",
        "What are the main services in this application?",
        "How does the chat service work?",
    ]
    
    print("\n2. Asking questions...")
    for i, question in enumerate(questions, 1):
        print(f"\n   Q{i}: {question}")
        response = client.chat(question)
        print(f"   A{i}: {response['message'][:200]}...")
        
        if response['sources']:
            print(f"   Sources ({len(response['sources'])}):")
            for source in response['sources'][:3]:  # Show first 3
                print(f"      - {source['file_name']}")
        
        time.sleep(1)  # Be nice to the API
    
    # Search the codebase
    print("\n3. Searching codebase...")
    search_query = "authentication"
    results = client.search(search_query, top_k=3)
    print(f"   Found {len(results)} results for '{search_query}':")
    for i, result in enumerate(results, 1):
        print(f"   {i}. {result['metadata'].get('file_name', 'Unknown')} (score: {result['score']:.2f})")
    
    # List all sessions
    print("\n4. Listing all sessions...")
    sessions = client.list_sessions()
    print(f"   Total sessions: {len(sessions)}")
    
    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    try:
        demo()
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to the server.")
        print("Make sure the Django server is running:")
        print("  python src/manage.py runserver")
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

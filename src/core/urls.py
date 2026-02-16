from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create router for viewsets
router = DefaultRouter()
router.register(r'sessions', views.ChatSessionViewSet, basename='chat-session')

urlpatterns = [
    path('', views.chatbot_ui, name='chatbot_ui'),  # Main chatbot UI
    path('health/', views.health_check, name='health_check'),
    
    # Chat endpoints
    path('api/chat/', views.ChatView.as_view(), name='chat'),
    path('api/', include(router.urls)),
    
    # Indexing endpoints
    path('api/index/', views.IndexingView.as_view(), name='index'),
    path('api/search/', views.SearchView.as_view(), name='search'),
]

from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('generate-lesson/', views.generate_lesson_view, name='generate_lesson'),
    path('my-lessons/', views.my_lessons_view, name='my_lessons'),
    path('lesson/<int:lesson_id>/', views.lesson_detail, name='lesson_detail'),
    path('conversation/', views.conversation_view, name='conversation'),
    path('progress/', views.progress_view, name='progress'),
    path('library/', views.library_view, name='library'),
    path('library/book/<int:book_id>/', views.book_detail, name='book_detail'),
    path('superuser/generate-book/', views.admin_generate_book, name='admin_generate_book'),
    path('superuser/book/<int:book_id>/preview/', views.admin_book_preview, name='admin_book_preview'),
    path('superuser/book/<int:book_id>/generate-content/', views.admin_generate_book_content, name='admin_generate_book_content'),
    path('superuser/book/<int:book_id>/publish/', views.admin_publish_book, name='admin_publish_book'),
    path('superuser/book/<int:book_id>/unpublish/', views.admin_unpublish_book, name='admin_unpublish_book'),
    path('superuser/book/<int:book_id>/delete/', views.admin_delete_book, name='admin_delete_book'),
    path('chat-api/', views.chat_api, name='chat_api'),
    path('voice-chat-api/', views.voice_chat_api, name='voice_chat_api'),
    path('api/update-time/', views.update_practice_time, name='update_practice_time'),
    path('generation/<int:task_id>/', views.generation_status, name='generation_status'),
    path('api/generation/<int:task_id>/', views.generation_status_api, name='generation_status_api'),
    path('lesson/<int:lesson_id>/regenerate/', views.regenerate_lesson, name='regenerate_lesson'),
    path('superuser/book/<int:book_id>/regenerate/', views.regenerate_book, name='regenerate_book'),
    path('superuser/chapter/<int:chapter_id>/regenerate/', views.regenerate_chapter, name='regenerate_chapter'),
]

from django.contrib import admin
from .models import Topic, Lesson, UserProgress, Conversation, Book, GenerationTask


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'created_at')
    list_filter = ('level',)
    search_fields = ('name',)
    ordering = ('-created_at',)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'topic', 'created_at')
    list_filter = ('topic__level', 'created_at')
    search_fields = ('title', 'summary', 'user__username')
    ordering = ('-created_at',)
    raw_id_fields = ('user', 'topic')


@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_level', 'practice_time_minutes', 'current_streak', 'last_activity_date')
    list_filter = ('current_level',)
    search_fields = ('user__username',)
    raw_id_fields = ('user',)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('user', 'started_at')
    list_filter = ('started_at',)
    search_fields = ('user__username',)
    ordering = ('-started_at',)
    raw_id_fields = ('user',)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'level', 'is_published', 'created_at')
    list_filter = ('level', 'is_published')
    search_fields = ('title', 'description')
    ordering = ('-created_at',)


@admin.register(GenerationTask)
class GenerationTaskAdmin(admin.ModelAdmin):
    list_display = ('task_type', 'topic', 'user', 'status', 'created_at', 'completed_at')
    list_filter = ('task_type', 'status', 'level')
    search_fields = ('topic', 'user__username')
    ordering = ('-created_at',)
    raw_id_fields = ('user',)
    readonly_fields = ('result_id', 'error_message', 'completed_at')

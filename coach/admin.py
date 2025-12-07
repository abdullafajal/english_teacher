from django.contrib import admin
from .models import Topic, Lesson, UserProgress, Conversation, Book, Chapter, GenerationTask


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


class ChapterInline(admin.TabularInline):
    """Inline editor for chapters within a book."""
    model = Chapter
    extra = 1
    ordering = ['order']
    fields = ('order', 'title', 'summary')
    show_change_link = True


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'level', 'chapter_count', 'is_published', 'created_at')
    list_filter = ('level', 'is_published')
    search_fields = ('title', 'description')
    ordering = ('-created_at',)
    inlines = [ChapterInline]
    
    def chapter_count(self, obj):
        return obj.chapters.count()
    chapter_count.short_description = 'Chapters'


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ('title', 'book', 'order', 'has_content', 'created_at')
    list_filter = ('book', 'created_at')
    search_fields = ('title', 'book__title')
    ordering = ('book', 'order')
    raw_id_fields = ('book',)
    
    def has_content(self, obj):
        return bool(obj.content)
    has_content.boolean = True
    has_content.short_description = 'Has Content'


@admin.register(GenerationTask)
class GenerationTaskAdmin(admin.ModelAdmin):
    list_display = ('task_type', 'topic', 'user', 'status', 'created_at', 'completed_at')
    list_filter = ('task_type', 'status', 'level')
    search_fields = ('topic', 'user__username')
    ordering = ('-created_at',)
    raw_id_fields = ('user',)
    readonly_fields = ('result_id', 'error_message', 'completed_at')

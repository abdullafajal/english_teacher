from django.db import models
from django.contrib.auth.models import User

class Topic(models.Model):
    LEVEL_CHOICES = [
        ('A1', 'Beginner'),
        ('A2', 'Elementary'),
        ('B1', 'Intermediate'),
        ('B2', 'Upper Intermediate'),
        ('C1', 'Advanced'),
        ('C2', 'Expert'),
    ]
    name = models.CharField(max_length=200)
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.level})"

class Lesson(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    summary = models.TextField()
    content = models.TextField(help_text="Markdown content")
    exercises = models.JSONField(default=dict)
    quiz = models.JSONField(default=dict)
    conversational_practice = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class UserProgress(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    current_level = models.CharField(max_length=2, choices=Topic.LEVEL_CHOICES, default='A1')
    completed_lessons = models.ManyToManyField(Lesson, blank=True)
    practice_time_minutes = models.IntegerField(default=0)
    words_learned = models.IntegerField(default=0)
    current_streak = models.IntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.current_level}"

class Conversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    history = models.JSONField(default=list)

    def __str__(self):
        return f"Conversation with {self.user.username} at {self.started_at}"

class Book(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    level = models.CharField(max_length=2, choices=Topic.LEVEL_CHOICES)
    content = models.JSONField(help_text="List of chapters")
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class GenerationTask(models.Model):
    """Track background content generation tasks."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    TYPE_CHOICES = [
        ('lesson', 'Lesson'),
        ('book', 'Book'),
        ('chapter', 'Chapter'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    task_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    topic = models.CharField(max_length=200)
    level = models.CharField(max_length=2)
    result_id = models.IntegerField(null=True, blank=True)  # ID of created lesson/book
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.task_type} - {self.topic} ({self.status})"


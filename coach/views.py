from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.cache import cache
from functools import wraps
from .models import Topic, Lesson, Book, Chapter, UserProgress, GenerationTask
from .services import AICoach
from django.contrib.auth.decorators import login_required
import markdown
import threading
import json
import time


# Rate Limiter - 15 requests per minute per user (safety margin for 20 RPM limit)
def rate_limit(requests_per_minute=15):
    """Decorator to rate limit API endpoints per user."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({'error': 'Authentication required'}, status=401)
            
            # Create cache key for user
            user_id = request.user.id
            cache_key = f'rate_limit_{user_id}'
            
            # Get current request timestamps
            now = time.time()
            timestamps = cache.get(cache_key, [])
            
            # Remove timestamps older than 1 minute
            cutoff = now - 60
            timestamps = [t for t in timestamps if t > cutoff]
            
            # Check if over limit
            if len(timestamps) >= requests_per_minute:
                wait_time = int(60 - (now - timestamps[0]))
                
                # Check if AJAX/API request
                is_ajax = request.headers.get('Content-Type') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                
                if is_ajax:
                    return JsonResponse({
                        'error': f'Rate limit exceeded. Please wait {wait_time} seconds.',
                        'rate_limited': True,
                        'wait_seconds': wait_time
                    }, status=429)
                else:
                    # For page requests, add message and redirect
                    from django.contrib import messages
                    messages.error(request, f'Rate limit exceeded. Please wait {wait_time} seconds before generating more content.')
                    return redirect('home')
            
            # Add current timestamp and save
            timestamps.append(now)
            cache.set(cache_key, timestamps, 120)  # Cache for 2 minutes
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


@login_required
def home(request):
    # Show only recent 3 lessons on dashboard
    recent_lessons = Lesson.objects.all().order_by('-created_at')[:3]
    
    # Get or create user progress
    progress, created = UserProgress.objects.get_or_create(user=request.user)
    
    return render(request, 'home.html', {
        'lessons': recent_lessons,
        'progress': progress
    })

@login_required
def my_lessons_view(request):
    # Show only user's own lessons
    lessons = Lesson.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'lesson_list.html', {'lessons': lessons})

@login_required
@rate_limit(requests_per_minute=15)
def generate_lesson_view(request):
    if request.method == 'POST':
        topic_name = request.POST.get('topic')
        level = request.POST.get('level')
        
        # Create a task to track generation
        task = GenerationTask.objects.create(
            user=request.user,
            task_type='lesson',
            topic=topic_name,
            level=level,
            status='pending'
        )
        
        # Start background generation
        thread = threading.Thread(
            target=generate_lesson_background,
            args=(task.id, topic_name, level)
        )
        thread.daemon = True
        thread.start()
        
        # Redirect to loader page
        return redirect('generation_status', task_id=task.id)
    
    return render(request, 'lesson_form.html')


def generate_lesson_background(task_id, topic_name, level):
    """Background function to generate lesson content."""
    import django
    django.db.connection.close()  # Close inherited connection
    
    try:
        task = GenerationTask.objects.get(id=task_id)
        task.status = 'processing'
        task.save()
        
        # Generate content
        coach = AICoach()
        lesson_data = coach.generate_lesson(topic_name, level)
        
        # Get or create topic
        topic, _ = Topic.objects.get_or_create(name=topic_name, level=level)
        
        # Save lesson with user from task
        lesson = Lesson.objects.create(
            user=task.user,
            topic=topic,
            title=lesson_data.get('title', 'Untitled Lesson'),
            summary=lesson_data.get('summary', ''),
            content=lesson_data.get('full_content', ''),
            exercises=lesson_data.get('exercises', {}),
            quiz=lesson_data.get('quiz', {}),
            conversational_practice=lesson_data.get('conversational_practice', '')
        )
        
        # Update task as completed
        task.status = 'completed'
        task.result_id = lesson.id
        task.completed_at = timezone.now()
        task.save()
        
    except Exception as e:
        task = GenerationTask.objects.get(id=task_id)
        task.status = 'failed'
        task.error_message = str(e)
        task.save()


@login_required
def generation_status(request, task_id):
    """Show loading page for background generation."""
    task = get_object_or_404(GenerationTask, id=task_id, user=request.user)
    return render(request, 'generation_loading.html', {'task': task})


@login_required
def generation_status_api(request, task_id):
    """API to check generation status."""
    task = get_object_or_404(GenerationTask, id=task_id, user=request.user)
    
    data = {
        'status': task.status,
        'task_type': task.task_type,
        'topic': task.topic,
    }
    
    if task.status == 'completed':
        if task.task_type == 'lesson':
            data['redirect_url'] = f'/lesson/{task.result_id}/'
        elif task.task_type == 'book':
            data['redirect_url'] = f'/superuser/book/{task.result_id}/preview/'
        elif task.task_type == 'chapter':
            data['redirect_url'] = f'/library/book/{task.result_id}/'
    elif task.status == 'failed':
        data['error'] = task.error_message
    
    return JsonResponse(data)


@login_required
def lesson_detail(request, lesson_id):
    # Only allow viewing own lessons (or admin can view all)
    if request.user.is_superuser:
        lesson = get_object_or_404(Lesson, pk=lesson_id)
    else:
        lesson = get_object_or_404(Lesson, pk=lesson_id, user=request.user)
    
    # Mark as completed (Simple logic for now: viewing = completing)
    progress, created = UserProgress.objects.get_or_create(user=request.user)
    
    # Only add practice time if this is the first time completing the lesson
    if lesson not in progress.completed_lessons.all():
        progress.practice_time_minutes += 10 # Assume 10 mins per lesson
        progress.completed_lessons.add(lesson)
    
    # Update Streak Logic
    from django.utils import timezone
    today = timezone.now().date()
    
    if progress.last_activity_date != today:
        if progress.last_activity_date == today - timezone.timedelta(days=1):
            # Consecutive day, increment streak
            progress.current_streak += 1
        else:
            # Missed a day or first day, reset to 1
            progress.current_streak = 1
        
        progress.last_activity_date = today
        progress.save()
    
    # Convert markdown content to HTML
    lesson.content_html = markdown.markdown(lesson.content)
    return render(request, 'lesson_detail.html', {'lesson': lesson})


@login_required
@rate_limit(requests_per_minute=15)
def regenerate_lesson(request, lesson_id):
    """Regenerate a lesson's content."""
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    
    # Create task for tracking
    task = GenerationTask.objects.create(
        user=request.user,
        task_type='lesson',
        topic=lesson.topic.name,
        level=lesson.topic.level,
        status='pending'
    )
    
    # Start background regeneration
    thread = threading.Thread(
        target=regenerate_lesson_background,
        args=(task.id, lesson.id)
    )
    thread.daemon = True
    thread.start()
    
    return redirect('generation_status', task_id=task.id)


def regenerate_lesson_background(task_id, lesson_id):
    """Background function to regenerate lesson content."""
    import django
    django.db.connection.close()
    
    try:
        task = GenerationTask.objects.get(id=task_id)
        task.status = 'processing'
        task.save()
        
        lesson = Lesson.objects.get(id=lesson_id)
        coach = AICoach()
        lesson_data = coach.generate_lesson(lesson.topic.name, lesson.topic.level)
        
        # Update existing lesson
        lesson.title = lesson_data.get('title', lesson.title)
        lesson.summary = lesson_data.get('summary', '')
        lesson.content = lesson_data.get('full_content', '')
        lesson.exercises = lesson_data.get('exercises', {})
        lesson.quiz = lesson_data.get('quiz', {})
        lesson.conversational_practice = lesson_data.get('conversational_practice', '')
        lesson.save()
        
        task.status = 'completed'
        task.result_id = lesson.id
        task.completed_at = timezone.now()
        task.save()
        
    except Exception as e:
        task = GenerationTask.objects.get(id=task_id)
        task.status = 'failed'
        task.error_message = str(e)
        task.save()


@login_required
def conversation_view(request):
    return render(request, 'conversation.html')

@login_required
def progress_view(request):
    progress, created = UserProgress.objects.get_or_create(user=request.user)
    
    # Chart Data: Voice Sessions over last 7 days
    from django.utils import timezone
    from django.db.models import Count
    from django.db.models.functions import TruncDate
    import datetime
    
    today = timezone.now().date()
    last_7_days = today - datetime.timedelta(days=6)
    
    sessions = Conversation.objects.filter(
        user=request.user,
        started_at__date__gte=last_7_days
    ).annotate(date=TruncDate('started_at')).values('date').annotate(count=Count('id')).order_by('date')
    
    # Format for Chart.js
    labels = []
    data = []
    
    # Fill in missing days
    current_date = last_7_days
    session_dict = {s['date']: s['count'] for s in sessions}
    
    for i in range(7):
        labels.append(current_date.strftime('%a')) # Mon, Tue, etc.
        data.append(session_dict.get(current_date, 0))
        current_date += datetime.timedelta(days=1)
        
    return render(request, 'progress.html', {
        'progress': progress,
        'chart_labels': labels,
        'chart_data': data
    })

@login_required
def library_view(request):
    books = Book.objects.filter(is_published=True).order_by('-created_at')
    return render(request, 'library.html', {'books': books})

@login_required
def book_detail(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    # Convert markdown content for each chapter
    from markdown_it import MarkdownIt
    from mdit_py_plugins.tasklists import tasklists_plugin
    from mdit_py_plugins.container import container_plugin
    from mdit_py_plugins.deflist import deflist_plugin
    
    md = (
        MarkdownIt('commonmark' , {'breaks':True, 'html':True})
        .enable('table')
        .enable('strikethrough')
        .use(tasklists_plugin)
        .use(container_plugin, name='warning')
        .use(container_plugin, name='tip')
        .use(deflist_plugin)
    )

    # Use Chapter model if available, fallback to JSON content
    chapters = []
    db_chapters = book.chapters.all().order_by('order')
    
    if db_chapters.exists():
        # Use Chapter model
        for chapter in db_chapters:
            chapters.append({
                'id': chapter.id,
                'title': chapter.title,
                'summary': chapter.summary,
                'content': chapter.content,
                'content_html': md.render(chapter.content) if chapter.content else '',
            })
    else:
        # Fallback to JSON content field
        json_chapters = book.content.get('chapters', []) if book.content else []
        for chapter in json_chapters:
            chapters.append({
                'title': chapter.get('title', ''),
                'summary': chapter.get('summary', ''),
                'content': chapter.get('content', ''),
                'content_html': md.render(chapter.get('content', '')) if chapter.get('content') else '',
            })
    
    return render(request, 'book_detail.html', {'book': book, 'chapters': chapters})

@login_required
@rate_limit(requests_per_minute=15)
def admin_generate_book(request):
    if not request.user.is_superuser:
        return redirect('home')
        
    if request.method == 'POST':
        topic = request.POST.get('topic')
        level = request.POST.get('level')
        
        # Create task for tracking
        task = GenerationTask.objects.create(
            user=request.user,
            task_type='book',
            topic=topic,
            level=level,
            status='pending'
        )
        
        # Start background generation
        thread = threading.Thread(
            target=generate_book_outline_background,
            args=(task.id, topic, level)
        )
        thread.daemon = True
        thread.start()
        
        return redirect('generation_status', task_id=task.id)
        
    books = Book.objects.all().order_by('-created_at')
    return render(request, 'admin_generate_book.html', {'books': books})


def generate_book_outline_background(task_id, topic, level):
    """Background function to generate book with chapters and content."""
    import django
    import traceback
    django.db.connection.close()
    
    try:
        task = GenerationTask.objects.get(id=task_id)
        task.status = 'processing'
        task.save()
        
        coach = AICoach()
        
        print(f"[Book Gen] Generating outline for: {topic}")
        book_data = coach.generate_book_outline(topic, level)
        
        # Create book
        book = Book.objects.create(
            title=book_data.get('title', 'Untitled Book'),
            description=book_data.get('description', ''),
            level=level,
            content={},  # Not using JSON anymore
            is_published=False
        )
        
        print(f"[Book Gen] Created book: {book.title}")
        
        # Create Chapter objects from outline AND generate content
        chapters_data = book_data.get('chapters', [])
        for i, chapter_data in enumerate(chapters_data):
            chapter_title = chapter_data.get('title', f'Chapter {i+1}')
            print(f"[Book Gen] Generating chapter {i+1}/{len(chapters_data)}: {chapter_title}")
            
            # Generate content for this chapter
            try:
                content_data = coach.generate_chapter_content(chapter_title, book.title, level)
                chapter_content = content_data.get('content', '')
            except Exception as ce:
                print(f"[Book Gen] Error generating chapter {i+1}: {ce}")
                chapter_content = f"Error generating content: {str(ce)}"
            
            # Create chapter with content
            Chapter.objects.create(
                book=book,
                title=chapter_title,
                summary=chapter_data.get('summary', ''),
                content=chapter_content,
                order=i
            )
            print(f"[Book Gen] Chapter {i+1} saved, content length: {len(chapter_content)}")
        
        print(f"[Book Gen] Completed book '{book.title}' with {len(chapters_data)} chapters")
        
        task.status = 'completed'
        task.result_id = book.id
        task.completed_at = timezone.now()
        task.save()
        
    except Exception as e:
        print(f"[Book Gen] FAILED: {str(e)}")
        traceback.print_exc()
        task = GenerationTask.objects.get(id=task_id)
        task.status = 'failed'
        task.error_message = str(e)
        task.save()


@login_required
def admin_book_preview(request, book_id):
    if not request.user.is_superuser:
        return redirect('home')
    book = get_object_or_404(Book, pk=book_id)
    return render(request, 'admin_book_preview.html', {'book': book})


@login_required
@rate_limit(requests_per_minute=15)
def admin_generate_book_content(request, book_id):
    if not request.user.is_superuser:
        return redirect('home')
    
    book = get_object_or_404(Book, pk=book_id)
    
    # Create task for tracking
    task = GenerationTask.objects.create(
        user=request.user,
        task_type='chapter',
        topic=book.title,
        level=book.level,
        status='pending'
    )
    
    # Store book_id in result_id temporarily for reference
    task.result_id = book_id
    task.save()
    
    # Start background generation
    thread = threading.Thread(
        target=generate_book_content_background,
        args=(task.id, book_id)
    )
    thread.daemon = True
    thread.start()
    
    return redirect('generation_status', task_id=task.id)


def generate_book_content_background(task_id, book_id):
    """Background function to generate all chapter content."""
    import django
    import traceback
    django.db.connection.close()
    
    try:
        task = GenerationTask.objects.get(id=task_id)
        task.status = 'processing'
        task.save()
        
        book = Book.objects.get(id=book_id)
        coach = AICoach()
        
        # Use Chapter model
        db_chapters = book.chapters.all().order_by('order')
        
        print(f"[Chapter Gen] Starting for book: {book.title}, {db_chapters.count()} chapters")
        
        for i, chapter in enumerate(db_chapters):
            print(f"[Chapter Gen] Generating chapter {i+1}/{db_chapters.count()}: {chapter.title}")
            try:
                content_data = coach.generate_chapter_content(chapter.title, book.title, book.level)
                chapter.content = content_data.get('content', '')
                chapter.save()
                print(f"[Chapter Gen] Chapter {i+1} done, content length: {len(chapter.content)}")
            except Exception as chapter_error:
                print(f"[Chapter Gen] Error on chapter {i+1}: {str(chapter_error)}")
                chapter.content = f"Error generating content: {str(chapter_error)}"
                chapter.save()
        
        print(f"[Chapter Gen] All chapters complete for book: {book.title}")
        
        task.status = 'completed'
        task.result_id = book_id
        task.completed_at = timezone.now()
        task.save()
        
    except Exception as e:
        print(f"[Chapter Gen] FAILED: {str(e)}")
        print(traceback.format_exc())
        task = GenerationTask.objects.get(id=task_id)
        task.status = 'failed'
        task.error_message = str(e)
        task.save()


@login_required
def admin_publish_book(request, book_id):
    if not request.user.is_superuser:
        return redirect('home')
    book = get_object_or_404(Book, pk=book_id)
    book.is_published = True
    book.save()
    return redirect('library')

@login_required
def admin_unpublish_book(request, book_id):
    if not request.user.is_superuser:
        return redirect('home')
    book = get_object_or_404(Book, pk=book_id)
    book.is_published = False
    book.save()
    return redirect('admin_generate_book')


@login_required
def regenerate_book(request, book_id):
    """Regenerate a book's outline."""
    if not request.user.is_superuser:
        return redirect('home')
    
    book = get_object_or_404(Book, pk=book_id)
    
    task = GenerationTask.objects.create(
        user=request.user,
        task_type='book',
        topic=book.title,
        level=book.level,
        status='pending'
    )
    
    thread = threading.Thread(
        target=regenerate_book_background,
        args=(task.id, book.id)
    )
    thread.daemon = True
    thread.start()
    
    return redirect('generation_status', task_id=task.id)


def regenerate_book_background(task_id, book_id):
    """Background function to regenerate book outline."""
    import django
    django.db.connection.close()
    
    try:
        task = GenerationTask.objects.get(id=task_id)
        task.status = 'processing'
        task.save()
        
        book = Book.objects.get(id=book_id)
        coach = AICoach()
        book_data = coach.generate_book_outline(book.title.split(':')[0], book.level)
        
        # Update existing book
        book.title = book_data.get('title', book.title)
        book.description = book_data.get('description', '')
        book.content = book_data
        book.save()
        
        task.status = 'completed'
        task.result_id = book.id
        task.completed_at = timezone.now()
        task.save()
        
    except Exception as e:
        task = GenerationTask.objects.get(id=task_id)
        task.status = 'failed'
        task.error_message = str(e)
        task.save()


@login_required
def admin_delete_book(request, book_id):
    if not request.user.is_superuser:
        return redirect('home')
    book = get_object_or_404(Book, pk=book_id)
    book.delete()
    return redirect('admin_generate_book')

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Conversation

@login_required
@rate_limit(requests_per_minute=15)
def chat_api(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_message = data.get('message')
        conversation_id = data.get('conversation_id')
        
        # Get or create conversation
        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id, user=request.user)
                history = conversation.history
            except Conversation.DoesNotExist:
                return JsonResponse({'error': 'Conversation not found'}, status=404)
        else:
            conversation = Conversation.objects.create(user=request.user)
            history = []
        
        # Chat with AI
        coach = AICoach()
        # Convert history format if needed, Gemini expects specific format
        # For simplicity, we'll just pass the raw history if it matches or adapt it
        # Gemini history: [{"role": "user", "parts": ["..."]}, {"role": "model", "parts": ["..."]}]
        gemini_history = []
        for msg in history:
            gemini_history.append({"role": "user", "parts": [msg['user']]})
            gemini_history.append({"role": "model", "parts": [msg['ai']]})
            
        response_text = coach.chat(gemini_history, user_message)
        
        # Update history
        history.append({'user': user_message, 'ai': response_text})
        conversation.history = history
        conversation.save()
        
        # Update Practice Time (1 minute per interaction)
        progress, _ = UserProgress.objects.get_or_create(user=request.user)
        progress.practice_time_minutes += 1
        progress.save()
        
        return JsonResponse({
            'response': response_text,
            'conversation_id': conversation.id
        })
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
@login_required
def update_practice_time(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            minutes = data.get('minutes', 1)
            
            progress, _ = UserProgress.objects.get_or_create(user=request.user)
            progress.practice_time_minutes += int(minutes)
            progress.save()
            
            return JsonResponse({'status': 'success', 'new_total': progress.practice_time_minutes})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

import base64

@login_required
@rate_limit(requests_per_minute=15)
def voice_chat_api(request):
    """Handle voice input using audio data."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            audio_base64 = data.get('audio')
            mime_type = data.get('mime_type', 'audio/webm')
            conversation_id = data.get('conversation_id')
            
            if not audio_base64:
                return JsonResponse({'error': 'No audio data provided'}, status=400)
            
            # Get or create conversation
            if conversation_id:
                try:
                    conversation = Conversation.objects.get(id=conversation_id, user=request.user)
                    history = conversation.history
                except Conversation.DoesNotExist:
                    return JsonResponse({'error': 'Conversation not found'}, status=404)
            else:
                conversation = Conversation.objects.create(user=request.user)
                history = []
            
            # Build Gemini history
            gemini_history = []
            for msg in history:
                gemini_history.append({"role": "user", "parts": [msg['user']]})
                gemini_history.append({"role": "model", "parts": [msg['ai']]})
            
            # Chat with AI using audio
            coach = AICoach()
            response_text = coach.chat_with_audio(gemini_history, audio_base64, mime_type)
            
            # Update history (store a placeholder for audio message)
            history.append({'user': '[Voice Message]', 'ai': response_text})
            conversation.history = history
            conversation.save()
            
            # Update Practice Time
            progress, _ = UserProgress.objects.get_or_create(user=request.user)
            progress.practice_time_minutes += 1
            progress.save()
            
            return JsonResponse({
                'response': response_text,
                'conversation_id': conversation.id
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


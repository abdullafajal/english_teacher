from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from .models import Topic, Lesson, Book, UserProgress
from .services import AICoach
from django.contrib.auth.decorators import login_required
import markdown

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
    lessons = Lesson.objects.all().order_by('-created_at')
    return render(request, 'lesson_list.html', {'lessons': lessons})

@login_required
def generate_lesson_view(request):
    if request.method == 'POST':
        topic_name = request.POST.get('topic')
        level = request.POST.get('level')
        
        # Check if topic exists or create it
        topic, created = Topic.objects.get_or_create(name=topic_name, level=level)
        
        # Generate content
        coach = AICoach()
        lesson_data = coach.generate_lesson(topic_name, level)
        
        # Save lesson
        lesson = Lesson.objects.create(
            topic=topic,
            title=lesson_data.get('title', 'Untitled Lesson'),
            summary=lesson_data.get('summary', ''),
            content=lesson_data.get('full_content', ''),
            exercises=lesson_data.get('exercises', {}),
            quiz=lesson_data.get('quiz', {}),
            conversational_practice=lesson_data.get('conversational_practice', '')
        )
        
        return redirect('lesson_detail', lesson_id=lesson.id)
    
    return render(request, 'lesson_form.html')

@login_required
def lesson_detail(request, lesson_id):
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    
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

    chapters = book.content.get('chapters', [])
    for chapter in chapters:
        chapter['content_html'] = md.render(chapter['content'])
    return render(request, 'book_detail.html', {'book': book, 'chapters': chapters})

@login_required
def admin_generate_book(request):
    if not request.user.is_superuser:
        return redirect('home')
        
    if request.method == 'POST':
        topic = request.POST.get('topic')
        level = request.POST.get('level')
        
        coach = AICoach()
        # Step 1: Generate Outline
        book_data = coach.generate_book_outline(topic, level)
        
        book = Book.objects.create(
            title=book_data.get('title', 'Untitled Book'),
            description=book_data.get('description', ''),
            level=level,
            content=book_data, # Contains chapters with summaries but no content yet
            is_published=False
        )
        return redirect('admin_book_preview', book_id=book.id)
        
    books = Book.objects.all().order_by('-created_at')
    return render(request, 'admin_generate_book.html', {'books': books})

@login_required
def admin_book_preview(request, book_id):
    if not request.user.is_superuser:
        return redirect('home')
    book = get_object_or_404(Book, pk=book_id)
    return render(request, 'admin_book_preview.html', {'book': book})

@login_required
def admin_generate_book_content(request, book_id):
    if not request.user.is_superuser:
        return redirect('home')
        
    book = get_object_or_404(Book, pk=book_id)
    coach = AICoach()
    
    # Reload content to ensure we're working with dict
    book_content = book.content
    chapters = book_content.get('chapters', [])
    
    updated_chapters = []
    for chapter in chapters:
        # Step 2: Generate Content for each chapter
        content_data = coach.generate_chapter_content(chapter['title'], book.title, book.level)
        chapter['content'] = content_data.get('content', '')
        updated_chapters.append(chapter)
    
    book_content['chapters'] = updated_chapters
    book.content = book_content
    book.save()
    
    return redirect('book_detail', book_id=book.id)

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

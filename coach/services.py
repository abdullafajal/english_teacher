import google.generativeai as genai
from django.conf import settings
import json

# Fast prompt for voice conversations
VOICE_PROMPT = """
You are an AI English Speaking Coach for voice conversations.

CRITICAL RULES:
1. KEEP RESPONSES UNDER 2 SENTENCES - This is a voice call, be brief!
2. Speak naturally like a friend, not a textbook
3. If user makes grammar mistake, correct it quickly: "Great! Just say 'went' not 'go' for past tense."
4. Ask ONE follow-up question to keep conversation going
5. No markdown, no bullet points - plain spoken English only
6. Be warm, encouraging, and patient
"""

# Detailed prompt for content generation
CONTENT_PROMPT = """
You are an expert English language education content creator.

Your role is to generate high-quality, structured educational content including:
- Grammar lessons with clear explanations and examples
- Vocabulary lessons with context and usage
- Practice exercises and quizzes
- Book chapters with comprehensive coverage

Guidelines:
- Use clear, professional language
- Provide rich examples and explanations
- Structure content logically
- Include practical exercises
- Make content engaging and easy to understand
- Always follow the requested JSON structure exactly
"""


def get_ai_settings():
    """Get AI settings from dynamic preferences, falling back to env vars."""
    try:
        from dynamic_preferences.registries import global_preferences_registry
        global_prefs = global_preferences_registry.manager()
        
        # Get API key - preference first, then env var
        api_key = global_prefs.get('ai_settings__gemini_api_key', '')
        if not api_key:
            api_key = settings.GEMINI_API_KEY
        
        # Get models
        voice_model = global_prefs.get('ai_settings__voice_model', '') or 'gemini-2.5-flash'
        content_model = global_prefs.get('ai_settings__content_model', '') or 'gemini-2.5-flash'
    except Exception as e:
        print(f"[AI Settings] Could not load preferences: {e}, using defaults")
        api_key = settings.GEMINI_API_KEY
        voice_model = 'gemini-2.5-flash'
        content_model = 'gemini-2.5-flash'
    
    print(f"[AI Settings] Using voice_model={voice_model}, content_model={content_model}")
    
    return {
        'api_key': api_key,
        'voice_model': voice_model,
        'content_model': content_model,
    }


class AICoach:
    """AI Coach with separate models for voice (fast) and content (quality)."""
    
    def __init__(self):
        # Load settings from dynamic preferences
        ai_settings = get_ai_settings()
        
        genai.configure(api_key=ai_settings['api_key'])
        
        # Voice model for conversations
        self.voice_model = genai.GenerativeModel(
            model_name=ai_settings['voice_model'],
            system_instruction=VOICE_PROMPT
        )
        
        # Content model for generation
        self.content_model = genai.GenerativeModel(
            model_name=ai_settings['content_model'],
            system_instruction=CONTENT_PROMPT
        )

    def generate_content(self, prompt):
        """Generates content based on a prompt, expecting JSON output. Uses quality model."""
        response_text = ""
        try:
            print(f"[AI] Generating content, prompt length: {len(prompt)}")
            response = self.content_model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            response_text = response.text
            print(f"[AI] Got response, length: {len(response_text)}")
            result = json.loads(response_text)
            print(f"[AI] Parsed JSON successfully")
            return result
        except json.JSONDecodeError as je:
            print(f"[AI] JSON parse error: {je}")
            print(f"[AI] Raw response: {response_text[:500]}...")
            
            # Try to extract content from malformed JSON
            import re
            
            # Look for "content": "..." pattern
            content_match = re.search(r'"content"\s*:\s*"(.*?)(?:"\s*}|$)', response_text, re.DOTALL)
            if content_match:
                extracted_content = content_match.group(1)
                # Unescape common JSON escapes
                extracted_content = extracted_content.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                print(f"[AI] Extracted content from malformed JSON, length: {len(extracted_content)}")
                return {"content": extracted_content}
            
            # Look for markdown content directly (fallback)
            if "# " in response_text:
                # Find start of markdown content
                start_idx = response_text.find('# ')
                extracted = response_text[start_idx:].strip()
                # Remove trailing JSON artifacts
                if extracted.endswith('"}') or extracted.endswith('"'):
                    extracted = extracted.rstrip('"}').strip()
                print(f"[AI] Extracted markdown directly, length: {len(extracted)}")
                return {"content": extracted}
            
            return {
                "title": "Error Parsing Response",
                "description": f"JSON parse error: {str(je)}",
                "content": response_text[:1000] if response_text else "",
                "chapters": []
            }
        except Exception as e:
            print(f"[AI] Error generating content: {e}")
            import traceback
            traceback.print_exc()
            return {
                "title": "Error Generating Content",
                "summary": "There was an error generating the content.",
                "description": f"Error: {str(e)}",
                "full_content": f"Error details: {str(e)}",
                "content": "",
                "exercises": [],
                "quiz": [],
                "chapters": [],
                "conversational_practice": [{"speaker": "System", "text": "Error generating practice."}]
            }

    def chat(self, history, message):
        """Conducts a text conversation. Uses fast model."""
        try:
            chat_session = self.voice_model.start_chat(history=history)
            response = chat_session.send_message(
                message,
                generation_config={
                    "max_output_tokens": 150,  # Limit response length for speed
                    "temperature": 0.7,
                }
            )
            return response.text
        except Exception as e:
            return f"Sorry, connection error. Try again."

    def chat_with_audio(self, history, audio_data, mime_type="audio/webm"):
        """Conducts a conversation using audio input. Uses fast model."""
        try:
            audio_part = {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": audio_data
                }
            }
            
            chat_session = self.voice_model.start_chat(history=history)
            response = chat_session.send_message(
                [audio_part],  # Just send audio, system prompt handles context
                generation_config={
                    "max_output_tokens": 150,  # Limit response length for speed
                    "temperature": 0.7,
                }
            )
            return response.text
        except Exception as e:
            return f"I couldn't process your voice message. Please try again. (Error: {str(e)})"

    def generate_lesson(self, topic, level):
        """Generate a complete lesson. Uses quality model."""
        prompt = f"""
        Generate a complete English lesson for the topic '{topic}' at level '{level}'.
        Return the response in JSON format with the following structure:
        {{
            "title": "Lesson Title",
            "summary": "Short summary",
            "full_content": "Markdown content of the lesson",
            "exercises": [
                {{"question": "...", "options": ["..."], "answer": "..."}}
            ],
            "quiz": [
                {{"question": "...", "options": ["..."], "answer": "..."}}
            ],
            "conversational_practice": [
                {{"speaker": "Person A", "text": "..."}},
                {{"speaker": "Person B", "text": "..."}}
            ]
        }}
        """
        return self.generate_content(prompt)

    def generate_book_outline(self, topic, level):
        """Generate book outline. Uses quality model."""
        print(f"[AI] Generating book outline for: {topic} ({level})")
        prompt = f"""
        Create an educational book outline for learning English.
        Topic: {topic}
        Level: {level}
        
        Return a JSON object with this exact structure:
        {{
            "title": "A descriptive book title about {topic}",
            "description": "A 2-3 sentence description of what this book teaches",
            "chapters": [
                {{"title": "Chapter 1: Introduction", "summary": "Overview of the topic"}},
                {{"title": "Chapter 2: ...", "summary": "What this chapter covers"}}
            ]
        }}
        
        Create 5-8 chapters covering the topic progressively from basics to advanced.
        """
        result = self.generate_content(prompt)
        print(f"[AI] Book outline result: title={result.get('title', 'NONE')}, chapters={len(result.get('chapters', []))}")
        return result

    def generate_chapter_content(self, chapter_title, book_title, level):
        """Generate chapter content. Uses quality model."""
        print(f"[AI] Generating content for chapter: {chapter_title}")
        prompt = f"""
        Write educational content for this chapter in an English learning book.
        
        Book: {book_title}
        Chapter: {chapter_title}
        Level: {level}
        
        Write detailed, educational content in Markdown format.
        
        Include:
        - Introduction to the topic
        - Key concepts with clear explanations
        - At least 3-5 practical examples
        - Common mistakes to avoid
        - Practice tips
        - Summary
        
        Return JSON:
        {{
            "content": "# {chapter_title}\\n\\nYour markdown content here..."
        }}
        """
        result = self.generate_content(prompt)
        print(f"[AI] Chapter content length: {len(result.get('content', ''))}")
        return result

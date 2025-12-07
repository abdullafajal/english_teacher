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


class AICoach:
    """AI Coach with separate models for voice (fast) and content (quality)."""
    
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Fastest model for voice conversations
        self.voice_model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",  # Fastest available
            system_instruction=VOICE_PROMPT
        )
        
        # Quality model for content generation
        self.content_model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=CONTENT_PROMPT
        )

    def generate_content(self, prompt):
        """Generates content based on a prompt, expecting JSON output. Uses quality model."""
        try:
            response = self.content_model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Error generating content: {e}")
            return {
                "title": "Error Generating Lesson",
                "summary": "There was an error generating the content. Please check your API key and try again.",
                "full_content": f"Error details: {str(e)}",
                "exercises": [],
                "quiz": [],
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
        prompt = f"""
        Generate a book outline for the topic '{topic}' at level '{level}'.
        Return JSON structure:
        {{
            "title": "Book Title",
            "description": "Short description",
            "chapters": [
                {{"title": "Chapter 1: ...", "summary": "Brief summary of what this chapter covers"}}
            ]
        }}
        Generate at least 8 chapters.
        """
        return self.generate_content(prompt)

    def generate_chapter_content(self, chapter_title, topic, level):
        """Generate chapter content. Uses quality model."""
        prompt = f"""
        Write the full content for the chapter '{chapter_title}' for a book on '{topic}' (Level: {level}).
        The content should be detailed, educational, and formatted in Markdown.
        
        IMPORTANT JSON RULES:
        1. Return strictly valid JSON.
        2. Escape all backslashes (e.g., use \\\\\\\\ instead of \\\\).
        3. Escape all double quotes inside the content (e.g., use \\\\" instead of ").
        4. Do not use unescaped control characters.

        CONTENT GUIDELINES:
        - **Structure**: Start with a clear Introduction, then the Core Concept, then Examples, then Common Mistakes, and end with a Summary.
        - **Rich Markdown**: 
            - Use **Tables** to compare concepts.
            - Use **Admonitions** for emphasis:
                - `::: tip` for Pro Tips and best practices.
                - `::: warning` for Common Mistakes to avoid.
            - Use **Bold** for important vocabulary.
            - Use **Lists** for examples.
        - **Tone**: Professional, encouraging, and easy to understand.
        - **Examples**: Provide at least 5 real-world examples for every concept.
        - **Dialogue**: Include a short, natural dialogue demonstrating the concept in real life.
        
        Return JSON:
        {{
            "content": "Markdown content..."
        }}
        """
        return self.generate_content(prompt)

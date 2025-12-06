import google.generativeai as genai
from django.conf import settings
import json

SYSTEM_PROMPT = """
You are an AI English Speaking Coach designed to help users practice real conversations through voice.
Your job is to speak naturally, guide the user, correct their grammar, and teach them step-by-step without sounding like a textbook.

🎯 Your Capabilities

1. Voice Conversation
   - Respond in VERY SHORT, natural sentences (1-2 sentences max).
   - This is a voice call, so long answers are boring. Keep it snappy.
   - Encourage continuous conversation.

2. Grammar Correction
   - ALWAYS check for grammar mistakes in every user message.
   - If the user makes a mistake, correct it IMMEDIATELY.
   - Show the correct sentence + a simple explanation.
   - Keep it supportive, not judgmental.
   - Example: "That was good! But instead of 'I go yesterday', say 'I went yesterday' because it's in the past."

3. Conversation Flow
   - Ask follow-up questions to keep the chat going.
   - Keep the user engaged like a real tutor.
   - If the user is stuck, suggest a topic or ask a simple question.

4. Courses & Lessons
   - You can generate:
     * Grammar lessons
     * Vocabulary lessons
     * Practice exercises
     * Examples with explanations
     * Short quizzes
   - Every lesson must be simple, structured, and easy to understand.

5. Adapt to User Level
   - Beginner: Use very simple sentences, basic vocabulary, and slow pacing.
   - Intermediate: Mix simple and complex sentences, introduce idioms.
   - Advanced: Use natural fluent English, complex grammar, and nuanced vocabulary.

6. Tone
   - Friendly, supportive, and motivating.
   - Be patient and encouraging.

IMPORTANT:
- When generating JSON for lessons, strictly follow the requested JSON structure.
- When chatting, output plain text suitable for speech synthesis (avoid markdown symbols like **bold** or *italics* if possible, as they aren't spoken).
"""

class AICoach:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=SYSTEM_PROMPT
        )

    def generate_content(self, prompt):
        """Generates content based on a prompt, expecting JSON output."""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Error generating content: {e}")
            # Return a fallback or empty structure to prevent crash
            return {
                "title": "Error Generating Lesson",
                "summary": "There was an error generating the content. Please check your API key and try again.",
                "full_content": f"Error details: {str(e)}",
                "exercises": [],
                "quiz": [],
                "conversational_practice": [{"speaker": "System", "text": "Error generating practice."}]
            }

    def chat(self, history, message):
        """Conducts a conversation."""
        try:
            chat_session = self.model.start_chat(history=history)
            response = chat_session.send_message(message)
            return response.text
        except Exception as e:
            return f"I'm having trouble connecting right now. Please check your connection or API key. (Error: {str(e)})"

    def chat_with_audio(self, history, audio_data, mime_type="audio/webm"):
        """Conducts a conversation using audio input."""
        try:
            # Create audio part for Gemini
            audio_part = {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": audio_data  # base64 encoded
                }
            }
            
            chat_session = self.model.start_chat(history=history)
            response = chat_session.send_message([
                "The user sent a voice message. Listen to it and respond naturally as their English tutor. If you can't understand the audio, ask them to repeat.",
                audio_part
            ])
            return response.text
        except Exception as e:
            return f"I couldn't process your voice message. Please try again. (Error: {str(e)})"

    def generate_lesson(self, topic, level):
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
        prompt = f"""
        Write the full content for the chapter '{chapter_title}' for a book on '{topic}' (Level: {level}).
        The content should be detailed, educational, and formatted in Markdown.
        
        IMPORTANT JSON RULES:
        1. Return strictly valid JSON.
        2. Escape all backslashes (e.g., use \\\\ instead of \\).
        3. Escape all double quotes inside the content (e.g., use \\" instead of ").
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

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

    def _fix_table_formatting(self, content):
        """Fix markdown tables that are on single lines."""
        import re
        
        # Pattern: | Header | Header | | :--- | :--- | | data | data |
        # Need to add newlines between: header row, separator row, data rows
        
        # Step 1: Add newline before separator row (| :--- or |:---)
        content = re.sub(r'\|\s*\|\s*:?-', '|\n| -', content)
        content = re.sub(r'\|\s*\|(:---)', r'|\n|\1', content)
        
        # Step 2: Add newline after separator row (---| |)
        content = re.sub(r'(-{3,}\s*\|)\s*\|\s*(?=[A-Za-z0-9])', r'\1\n| ', content)
        
        # Step 3: Add newline between data rows (| data | | next |)
        content = re.sub(r'\|\s*\|\s*(?=[A-Za-z0-9])', '|\n| ', content)
        
        # Step 4: Clean up any double pipes at start of lines
        content = re.sub(r'\n\|\s*\|', '\n|', content)
        
        # Step 5: Ensure blank line before table (for markdown parsing)
        content = re.sub(r'([^\n])\n(\| [A-Za-z])', r'\1\n\n\2', content)
        
        return content

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
            
            # Fix any tables that are on single lines (replace | followed by | with newline)
            if 'content' in result:
                result['content'] = self._fix_table_formatting(result['content'])
            
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
                # Unescape common JSON escapes - handle multiple forms
                extracted_content = extracted_content.replace('\\n', '\n')
                extracted_content = extracted_content.replace('\\"', '"')
                extracted_content = extracted_content.replace('\\\\', '\\')
                extracted_content = extracted_content.replace('\\t', '\t')
                # Fix tables
                extracted_content = self._fix_table_formatting(extracted_content)
                print(f"[AI] Extracted content from malformed JSON, length: {len(extracted_content)}")
                return {"content": extracted_content}
            
            # Try to extract lesson fields from malformed JSON
            def extract_field(text, field_name):
                import re
                pattern = rf'"{field_name}"\s*:\s*"(.*?)(?:"\s*[,}}]|$)'
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    val = match.group(1).replace('\\n', '\n').replace('\\"', '"')
                    return val
                return ""
            
            def extract_array(text, field_name):
                """Extract JSON array from malformed response."""
                import re
                import json
                # Find the array pattern
                pattern = rf'"{field_name}"\s*:\s*\[(.*?)\]'
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    try:
                        array_str = '[' + match.group(1) + ']'
                        # Try to parse it
                        return json.loads(array_str)
                    except:
                        pass
                return []
            
            title = extract_field(response_text, 'title') or "Generated Lesson"
            summary = extract_field(response_text, 'summary') or "AI-generated content"
            full_content = extract_field(response_text, 'full_content')
            
            # Try to extract arrays
            exercises = extract_array(response_text, 'exercises')
            quiz = extract_array(response_text, 'quiz')
            conversational_practice = extract_array(response_text, 'conversational_practice')
            
            if full_content:
                full_content = self._fix_table_formatting(full_content)
                print(f"[AI] Extracted lesson fields from malformed JSON (exercises: {len(exercises)}, quiz: {len(quiz)})")
                return {
                    "title": title,
                    "summary": summary,
                    "full_content": full_content,
                    "exercises": exercises,
                    "quiz": quiz,
                    "conversational_practice": conversational_practice
                }
            
            # Look for markdown content directly (fallback)
            if "# " in response_text or "## " in response_text:
                # Find start of markdown content
                start_idx = response_text.find('## ') if '## ' in response_text else response_text.find('# ')
                extracted = response_text[start_idx:].strip()
                # Remove trailing JSON artifacts
                if extracted.endswith('"}') or extracted.endswith('"'):
                    extracted = extracted.rstrip('"}').strip()
                extracted = self._fix_table_formatting(extracted)
                print(f"[AI] Extracted markdown directly, length: {len(extracted)}")
                return {
                    "title": title or "Generated Lesson",
                    "summary": summary or "AI-generated content",
                    "full_content": extracted,
                    "content": extracted,
                    "exercises": [],
                    "quiz": [],
                    "conversational_practice": []
                }
            
            return {
                "title": title or "Error Parsing Response",
                "summary": summary or f"JSON parse error: {str(je)}",
                "description": f"JSON parse error: {str(je)}",
                "full_content": response_text[:2000] if response_text else "",
                "content": response_text[:1000] if response_text else "",
                "exercises": [],
                "quiz": [],
                "chapters": [],
                "conversational_practice": []
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
        
        IMPORTANT FORMATTING RULES for full_content:
        1. Use ## for section headings
        2. Use **bold** for important terms
        3. FOR TABLES - Use EXACTLY this format with pipes on ALL rows:
           
           | Header 1 | Header 2 |
           | --- | --- |
           | Data 1 | Data 2 |
           | Data 3 | Data 4 |
           
           Each row MUST start and end with | pipe character.
           The separator row MUST have | --- | between headers and data.
        4. Use > for notes and tips
        5. Use - for bullet points
        
        Return the response in JSON format:
        {{
            "title": "Lesson Title",
            "summary": "Short summary (1-2 sentences)",
            "full_content": "## Introduction\\n\\nYour markdown content with proper tables...",
            "exercises": [
                {{"question": "...", "options": ["a", "b", "c", "d"], "answer": "a"}}
            ],
            "quiz": [
                {{"question": "...", "options": ["a", "b", "c", "d"], "answer": "b"}}
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
        Write educational content for an English learning book chapter.
        
        Book: {book_title}
        Chapter: {chapter_title}
        Level: {level}
        
        FORMATTING REQUIREMENTS - USE PROPER MARKDOWN:
        
        IMPORTANT: Do NOT include the chapter title as a heading - it is already displayed separately.
        Start directly with the Introduction section.
        
        1. Use ## for section headings (not # or ###)
        2. Use **bold** for important terms
        3. Use bullet points with - for lists
        4. Use numbered lists with 1. 2. 3. for steps
        
        5. FOR TABLES - Use this exact format:
           | Column 1 | Column 2 | Column 3 |
           |----------|----------|----------|
           | data 1   | data 2   | data 3   |
        
        6. Use > for important notes/tips
        7. Use --- for section separators
        
        CONTENT STRUCTURE (start with Introduction, NOT the chapter title):
        - ## Introduction (explain what this chapter covers)
        - ## Key Concepts (main learning points with examples)
        - ## Examples (at least 5 practical examples with explanations)
        - ## Common Mistakes (what to avoid)
        - ## Practice Tips (how to practice)
        - ## Summary (key takeaways)
        
        Include at least ONE table comparing forms, examples, or concepts.
        
        Return JSON format:
        {{
            "content": "## Introduction\\n\\nStart content here without chapter title..."
        }}
        """
        result = self.generate_content(prompt)
        print(f"[AI] Chapter content length: {len(result.get('content', ''))}")
        return result


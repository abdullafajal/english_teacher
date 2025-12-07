# coach/dynamic_preferences_registry.py
"""
Dynamic preferences for AI Coach configuration.
These can be changed from Django Admin without restart.
"""

from dynamic_preferences.types import StringPreference, ChoicePreference
from dynamic_preferences.preferences import Section
from dynamic_preferences.registries import global_preferences_registry

# Create sections
ai_settings = Section('ai_settings')


@global_preferences_registry.register
class GeminiAPIKey(StringPreference):
    """Gemini API Key for AI generation."""
    section = ai_settings
    name = 'gemini_api_key'
    default = ''
    verbose_name = 'Gemini API Key'
    help_text = 'Your Google Gemini API key'
    required = False


@global_preferences_registry.register
class VoiceModel(StringPreference):
    """Model for voice/chat interactions (faster)."""
    section = ai_settings
    name = 'voice_model'
    default = 'gemini-2.5-flash'
    verbose_name = 'Voice Model'
    help_text = 'Model for real-time voice conversations (use faster models like gemini-2.0-flash)'
    required = False


@global_preferences_registry.register
class ContentModel(StringPreference):
    """Model for content generation (better quality)."""
    section = ai_settings
    name = 'content_model'
    default = 'gemini-2.5-flash'
    verbose_name = 'Content Generation Model'
    help_text = 'Model for generating lessons, books, chapters (use quality models like gemini-2.5-flash)'
    required = False

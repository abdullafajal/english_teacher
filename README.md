# AI English Teacher

An intelligent, voice-interactive English learning platform powered by Google Gemini AI. This application acts as a personal English coach, helping users practice conversation, reading, and grammar through natural voice interactions.

## 🚀 Features

-   **AI Voice Coach**: Real-time voice conversation with an AI tutor using Web Speech API and Gemini.
    -   *Voice 2.0*: Robust "Always On" microphone handling with barge-in interruption capability.
    -   *Natural TTS*: Uses browser-native text-to-speech with customizable speed and pitch.
-   **Interactive Library**: Read books with AI-generated explanations, vocabulary highlighting, and quizzes.
-   **Progress Tracking**: Track practice time, lessons completed, and daily streaks.
-   **Smart Content**: AI-generated lessons, quizzes, and book chapters tailored to the user's level.
-   **Responsive Design**: Mobile-first UI built with Tailwind CSS and Material Design 3 principles.

## 🛠️ Tech Stack

-   **Backend**: Django 5.x (Python)
-   **Frontend**: HTML5, Tailwind CSS, Vanilla JavaScript
-   **AI**: Google Gemini API (via `google-generativeai`)
-   **Voice**: Web Speech API (SpeechRecognition & SpeechSynthesis)
-   **Database**: SQLite (Development) / PostgreSQL (Production ready)

## 📦 Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/yourusername/english-teacher.git
    cd english-teacher
    ```

2.  **Create a virtual environment**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up Environment Variables**
    Create a `.env` file in the root directory:
    ```env
    DEBUG=True
    SECRET_KEY=your-secret-key
    GEMINI_API_KEY=your-gemini-api-key
    ```

5.  **Run Migrations**
    ```bash
    python manage.py migrate
    ```

6.  **Start the Server**
    ```bash
    python manage.py runserver
    ```

## 📱 Mobile Usage

The application is optimized for mobile devices.
-   **Microphone**: Ensure you grant microphone permissions in your browser.
-   **Voice Interaction**: Tap the mic once to start. The AI listens continuously. You can interrupt the AI at any time by speaking.

## 🤝 Contributing

1.  Fork the project
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

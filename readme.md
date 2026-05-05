# Campus Digital Ecosystem

A modern, responsive, and robust college management platform built with Flask. The system unifies attendance tracking, student resources, an AI-powered study assistant, and role-based access control into a single cohesive "Campus OS".

## 🚀 Features

- **Dynamic Dashboard**: Personalized view for Admins, Faculty, and Students including a dynamic timetable grid.
- **Attendance Hub**:
  - Secure QR-code based attendance scanning.
  - Granular session management and comprehensive CSV export capabilities for faculty.
  - Role-based access control to prevent proxy attendance.
- **Study AI (Concept Chef)**:
  - Generates interactive study materials (summaries, analogies, Mermaid JS mind maps, quizzes).
  - Can ingest text, PDFs, or YouTube URLs (via transcripts).
  - Includes an embedded chat widget for active recall and tutoring.
- **Notes Hub**: A centralized repository for sharing and accessing PDF resources.
- **Admin Panel**: Tools to manage student registrations, device binding resets, and platform configuration.
- **Premium UI/UX**: Neo-editorial design system featuring a dynamic dark/light mode, custom glassmorphism, fluid typography, and a reactive cursor spotlight.

## 🛠️ Technology Stack

- **Backend**: Python 3, Flask, SQLite
- **Frontend**: HTML5, CSS3 (Custom Tokens & Components), Vanilla JavaScript
- **AI Integrations**: Google Gemini API (`gemini-2.5-flash`), YouTube Transcript API, PyPDF2
- **Deployment**: Configured for serverless deployment on Vercel (`vercel.json` included)

## 💻 Local Setup & Development

### 1. Prerequisites

- Python 3.10+
- Git

### 2. Installation

Clone the repository and navigate into the project directory:

```bash
git clone <your-repo-url>
cd clgeco
```

Create a virtual environment and activate it:

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the root directory and add your API keys and secrets:

```env
# Required for the Study AI module
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Set a custom secret key for Flask sessions
FLASK_SECRET_KEY=your_super_secret_key
```

### 4. Running the Application

Start the development server:

```bash
python main.py
```

The application will be available at `http://127.0.0.1:5000`.

## 🌐 Deployment to Vercel

This project is configured for Vercel deployment out-of-the-box. The `vercel.json` file handles routing and specifies the Python runtime.

1. Install the Vercel CLI or use the Vercel Dashboard.
2. Ensure you add `GEMINI_API_KEY` to your Vercel project's Environment Variables.
3. Deploy!

*Note regarding SQLite on Vercel: Vercel's file system is ephemeral. The current configuration uses `/tmp` for database and file uploads during deployment to prevent crash errors, but data will be lost between serverless function invocations. For a production deployment on Vercel, you should migrate the SQLite database to a hosted solution like Supabase, PlanetScale, or a PostgreSQL instance.*

## 📂 Project Structure

```
├── main.py                 # Application entry point and configuration
├── .env                    # Environment variables (not tracked by git)
├── .gitignore              # Git ignore rules
├── requirements.txt        # Python dependencies
├── vercel.json             # Vercel deployment configuration
├── routes/                 # Flask Blueprints
│   ├── attendance_api.py
│   ├── auth_api.py
│   └── study_api.py
├── templates/              # Jinja2 HTML Templates
│   ├── _partials/          # Shared layout components (header, footer, nav)
│   ├── dashboard.html
│   ├── login.html
│   ├── notes.html
│   └── study.html
└── static/                 # Static Assets
    ├── css/
    │   ├── tokens.css      # Design system variables
    │   └── components.css  # Reusable UI components
    └── js/
        ├── animations.js
        ├── cursor.js       # Dynamic cursor spotlight effect
        └── theme.js        # Dark/Light mode toggle logic
```

## 🔒 Security Notes

- Device bindings are stored in the database to prevent proxy attendance logging.
- The `.env` file is included in `.gitignore` to prevent leaking API keys. Always keep your `GEMINI_API_KEY` private.

## 🤝 Credits

Built by **Team RAGE** at AMC Engineering College.

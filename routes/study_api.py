import os
import json
import uuid
import re
from flask import Blueprint, render_template, request, jsonify

# New Google GenAI SDK (google-genai package)
from google import genai
from google.genai import types
from youtube_transcript_api import YouTubeTranscriptApi
from PyPDF2 import PdfReader

# ── Central config (change model/key in config.py) ──
from config import GEMINI_API_KEY, GEMINI_MODEL

# -------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------

study_bp = Blueprint('study', __name__)

# Configure the new SDK client
try:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set. Add it to your .env file or config.py.")
    _client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    _client = None

if os.environ.get('VERCEL'):
    UPLOAD_DIR = '/tmp/uploads'
else:
    UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory storage (resets when server restarts)
CONTENT_CACHE = {}

# -------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------

def extract_video_id(url: str) -> str:
    if not url: return None
    if "youtu.be/" in url: return url.split("youtu.be/")[1].split("?")[0]
    if "v=" in url: return url.split("v=")[1].split("&")[0]
    if "/embed/" in url: return url.split("/embed/")[1].split("?")[0]
    match = re.search(r"([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None

def get_transcript_data(video_id: str):
    try:
        api = YouTubeTranscriptApi()
        return api.fetch(video_id, languages=("en", "en-US", "en-IN", "hi")).to_raw_data()
    except Exception as e:
        error_msg = str(e).lower()
        if "blocking requests from your ip" in error_msg or "cloud provider" in error_msg or "vercel" in error_msg:
            raise ValueError("YouTube blocks automated transcript fetching from cloud servers. "
                             "Please use the 'Text' or 'PDF' tab to paste your content instead.")
        raise ValueError(f"No captions found. Error: {str(e)}")

def extract_pdf_text(filepath: str) -> str:
    try:
        reader = PdfReader(filepath)
        text = "\n".join([(page.extract_text() or "").strip() for page in reader.pages])
        return text
    except Exception as e:
        raise ValueError(f"PDF Error: {str(e)}")

def parse_gemini_json(text: str):
    """Robust JSON parser that handles common AI formatting quirks."""
    try:
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {e}")
        print(f"Bad JSON (first 500 chars): {text[:500]}")
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                return json.loads(text[start:end+1])
        except:
            pass
        raise ValueError("The AI generated invalid data. Please try again.")

# -------------------------------------------------------------
# AI LOGIC — New google.genai SDK
# -------------------------------------------------------------

def call_gemini(prompt: str, json_mode: bool = True) -> str:
    """Call Gemini using the new google.genai SDK."""
    if not _client:
        raise ValueError("Gemini client not configured. Check your API key in .env / config.py.")

    config_kwargs = {}
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"

    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(**config_kwargs) if config_kwargs else None
    )
    return response.text

def build_prompt(raw_text: str, persona: str, q_count: int, difficulty: str, mode: str) -> str:

    # --- MODE 1: X-RAY (SCAFFOLDING) ---
    if mode == 'layered':
        schema = """
        [
          {
            "heading": "Main Heading",
            "subsections": [
              {
                "subheading": "Sub-point",
                "layer_3_concept": "One sentence core logic.",
                "layer_4_detail": "Full detailed explanation."
              }
            ]
          }
        ]
        """
        return (
            f"Persona: {persona}\n"
            f"Task: Break content into a 4-layer learning structure.\n"
            f"Output Requirement: VALID JSON only. Do NOT use markdown formatting. Escape all quotes inside strings.\n"
            f"Content:\n{raw_text[:40000]}\n\n"
            f"Use this Schema:\n{schema}"
        )

    # --- MODE 2: STANDARD MIX (QUIZ + MAP) ---
    schema = """
    {
      "summary": ["Bullet 1", "Bullet 2"],
      "analogy_title": "Title",
      "analogy_content": "Content...",
      "mind_map": "graph TD; A[Node] --> B[Node];",
      "quiz": [
        { "type": "mcq", "question": "...", "options": ["A","B"], "answer_index": 0, "feedback": "..." },
        { "type": "cloze", "question": "...", "sentence_with_blank": "The ____ is power.", "answer": "knowledge", "feedback": "..." }
      ]
    }
    """
    return (
        f"Persona: {persona}\n"
        f"Task: Create study material.\n"
        f"Output Requirement: VALID JSON only. No markdown. Escape inner quotes.\n"
        f"Quiz: {q_count} questions ({difficulty}). Mix 'mcq' and 'cloze'.\n"
        f"Mind Map: Mermaid JS. Wrap ALL node text in double quotes (e.g. A[\"Text\"]).\n"
        f"Content:\n{raw_text[:40000]}\n\n"
        f"Use this Schema:\n{schema}"
    )

# -------------------------------------------------------------
# ROUTES
# -------------------------------------------------------------

@study_bp.route('/', methods=['GET'])
def index():
    return render_template('study.html')

@study_bp.route('/generate', methods=['POST'])
def generate():
    try:
        source_type = request.form.get('source_type', '').strip().lower()
        style = request.form.get('style', 'Standard')
        q_count = int(request.form.get('q_count', '5'))
        gen_mode = request.form.get('gen_mode', 'standard')

        raw_text_full = ""
        video_id = None
        transcript_data = None

        # Source Handling
        if source_type == 'youtube':
            url = request.form.get('url', '')
            video_id = extract_video_id(url)
            if not video_id:
                raise ValueError("Could not extract video ID from URL.")
            transcript_data = get_transcript_data(video_id)
            raw_text_full = " ".join([item['text'] for item in transcript_data])
        elif source_type == 'pdf':
            if 'file' not in request.files: raise ValueError("No file part")
            f = request.files['file']
            if f.filename == '': raise ValueError("No selected file")
            save_path = os.path.join(UPLOAD_DIR, f.filename)
            f.save(save_path)
            raw_text_full = extract_pdf_text(save_path)
        elif source_type in ['text', 'gemini']:
            raw_text_full = request.form.get('text_content', '').strip()
            if source_type == 'gemini':
                raw_text_full = f"CONTEXT: Chat Log. Focus on concepts.\nLOG:\n{raw_text_full}"
            # Micro-Concept Logic
            if len(raw_text_full) < 500 and gen_mode == 'standard':
                q_count = 1
                style = "Strict Professor"

        if not raw_text_full:
            raise ValueError("No text could be extracted.")

        # Cache
        session_id = str(uuid.uuid4())
        CONTENT_CACHE[session_id] = {
            "text": raw_text_full,
            "meta": {"source": source_type, "style": style}
        }

        # Generate via new SDK
        prompt = build_prompt(raw_text_full, style, q_count, "Hard", gen_mode)
        response_text = call_gemini(prompt, json_mode=True)
        data = parse_gemini_json(response_text)

        return jsonify({
            "status": "success", "data": data,
            "video_id": video_id, "session_id": session_id, "mode": gen_mode
        })

    except Exception as e:
        print(f"SERVER ERROR in /generate: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400


@study_bp.route('/chat', methods=['POST'])
def chat():
    data = request.json
    session_id = data.get('session_id')
    user_msg = data.get('message')
    mode = data.get('mode', 'tutor')

    if not session_id or session_id not in CONTENT_CACHE:
        return jsonify({"reply": "Session expired. Please regenerate your study material."})

    context_str = CONTENT_CACHE[session_id]['text'][:30000]

    if mode == 'examiner':
        instructions = "You are a Strict Examiner. Test the user using Active Recall. Ask questions. Do not lecture."
    else:
        instructions = "You are a helpful Tutor. Explain clearly using the context."

    try:
        chat_prompt = f"{instructions}\n\nContext:\n{context_str}\n\nUser: {user_msg}"
        reply = call_gemini(chat_prompt, json_mode=False)
        return jsonify({"reply": reply})
    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({"reply": f"Error contacting AI: {str(e)}"})

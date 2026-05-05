from flask import Flask, render_template, request, session, redirect, url_for, flash, send_from_directory, abort
from datetime import timedelta, datetime
import sqlite3, os

from routes.study_api import study_bp
from routes.attendance_api import attendance_bp
from routes.auth_api import auth_bp

app = Flask(__name__)
# Configurations
app.secret_key = 'super_secret_key_campus'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB max upload
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # 30-day login persistence

# Upload folder — use /tmp on Vercel, local uploads/ otherwise
if os.environ.get('VERCEL'):
    UPLOAD_FOLDER = '/tmp/notes_uploads'
else:
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Notes DB
if os.environ.get('VERCEL'):
    NOTES_DB = '/tmp/notes.db'
else:
    NOTES_DB = os.path.join(os.path.dirname(__file__), 'database', 'notes.db')
os.makedirs(os.path.dirname(NOTES_DB), exist_ok=True)

def get_notes_db():
    conn = sqlite3.connect(NOTES_DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_notes_db():
    conn = get_notes_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            filename TEXT NOT NULL,
            uploader TEXT NOT NULL,
            uploaded_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_notes_db()

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(study_bp, url_prefix='/study')
app.register_blueprint(attendance_bp, url_prefix='/attendance')

@app.before_request
def require_login():
    allowed_endpoints = ['auth.login', 'static']
    if request.endpoint not in allowed_endpoints and not request.path.startswith('/static'):
        if not session.get('role'):
            return redirect(url_for('auth.login', next=request.url))

@app.route('/')
def index():
    return render_template('dashboard.html')

# ── Notes Routes ──────────────────────────────────────────────

@app.route('/notes')
def notes():
    conn = get_notes_db()
    rows = conn.execute('SELECT * FROM Notes ORDER BY uploaded_at DESC').fetchall()
    conn.close()
    return render_template('notes.html', notes=rows)

@app.route('/notes/upload', methods=['POST'])
def notes_upload():
    if session.get('role') not in ['admin', 'faculty']:
        abort(403)

    title   = request.form.get('title', '').strip()
    subject = request.form.get('subject', '').strip()
    pdf     = request.files.get('pdf')

    if not title or not subject or not pdf or pdf.filename == '':
        flash('Please fill all fields and select a PDF file.', 'error')
        return redirect(url_for('notes'))

    if not pdf.filename.lower().endswith('.pdf'):
        flash('Only PDF files are allowed.', 'error')
        return redirect(url_for('notes'))

    # Safe filename: timestamp + original name
    safe_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{pdf.filename.replace(' ', '_')}"
    save_path = os.path.join(UPLOAD_FOLDER, safe_name)
    pdf.save(save_path)

    conn = get_notes_db()
    conn.execute(
        'INSERT INTO Notes (title, subject, filename, uploader, uploaded_at) VALUES (?, ?, ?, ?, ?)',
        (title, subject, safe_name, session.get('id', 'Faculty'), datetime.now().strftime('%d %b %Y, %H:%M'))
    )
    conn.commit()
    conn.close()

    flash(f'"{title}" uploaded successfully.', 'success')
    return redirect(url_for('notes'))

@app.route('/notes/download/<int:note_id>')
def notes_download(note_id):
    conn = get_notes_db()
    note = conn.execute('SELECT * FROM Notes WHERE id = ?', (note_id,)).fetchone()
    conn.close()
    if not note:
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, note['filename'], as_attachment=True, download_name=note['title'] + '.pdf')

@app.route('/notes/view/<int:note_id>')
def notes_view(note_id):
    conn = get_notes_db()
    note = conn.execute('SELECT * FROM Notes WHERE id = ?', (note_id,)).fetchone()
    conn.close()
    if not note:
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, note['filename'], as_attachment=False)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

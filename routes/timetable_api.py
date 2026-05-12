"""
Timetable Blueprint
- Admin uploads timetable files (PDF/image) tagged with department + section OR teacher
- Students are auto-assigned a section based on USN number
  Example: 1AM24EC001-060 → Section A, 061-120 → B, 121-180 → C  (configurable per dept)
- Faculty see their personal timetable
- Admin can manage all uploaded timetables
"""
import os
import sqlite3
from datetime import datetime
from flask import (
    Blueprint, render_template, request, session,
    redirect, url_for, flash, send_from_directory, abort
)

timetable_bp = Blueprint('timetable', __name__)

# ── DB & Upload paths ──────────────────────────────────────────────────────────
if os.environ.get('VERCEL'):
    TT_DB      = '/tmp/timetable.db'
    TT_UPLOADS = '/tmp/timetable_uploads'
else:
    _base      = os.path.dirname(os.path.dirname(__file__))
    TT_DB      = os.path.join(_base, 'database', 'timetable.db')
    TT_UPLOADS = os.path.join(_base, 'uploads', 'timetable')

os.makedirs(TT_UPLOADS, exist_ok=True)
os.makedirs(os.path.dirname(TT_DB), exist_ok=True)


def get_db():
    conn = sqlite3.connect(TT_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS Timetables (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            label       TEXT NOT NULL,          -- e.g. "ECE – Section A" or "Prof. Sharma"
            dept        TEXT NOT NULL,          -- e.g. "ECE", "CSE", "TEACHER"
            section     TEXT,                   -- "A"/"B"/"C"/NULL for teacher rows
            target_type TEXT NOT NULL,          -- "student" | "teacher" | "common"
            filename    TEXT NOT NULL,
            uploader    TEXT NOT NULL,
            uploaded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS SectionRules (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            dept        TEXT NOT NULL,
            section     TEXT NOT NULL,
            usn_prefix  TEXT NOT NULL,          -- e.g. "1AM24EC"
            usn_from    INTEGER NOT NULL,
            usn_to      INTEGER NOT NULL
        );
    ''')
    # Seed default section rules for ECE 2024 batch if none exist
    existing = conn.execute("SELECT COUNT(*) FROM SectionRules").fetchone()[0]
    if existing == 0:
        defaults = [
            ('ECE', 'A', '1AM24EC',   1,  60),
            ('ECE', 'B', '1AM24EC',  61, 120),
            ('ECE', 'C', '1AM24EC', 121, 180),
            ('CSE', 'A', '1AM24CS',   1,  60),
            ('CSE', 'B', '1AM24CS',  61, 120),
            ('CSE', 'C', '1AM24CS', 121, 180),
            ('ISE', 'A', '1AM24IS',   1,  60),
            ('ISE', 'B', '1AM24IS',  61, 120),
            ('ME',  'A', '1AM24ME',   1,  60),
            ('ME',  'B', '1AM24ME',  61, 120),
        ]
        conn.executemany(
            "INSERT INTO SectionRules (dept, section, usn_prefix, usn_from, usn_to) VALUES (?,?,?,?,?)",
            defaults
        )
    conn.commit()
    conn.close()


def resolve_student_section(usn: str):
    """Return (dept, section) for a student USN, e.g. '1AM24EC043' → ('ECE', 'A')."""
    usn = usn.upper().strip()
    conn = get_db()
    rules = conn.execute("SELECT * FROM SectionRules").fetchall()
    conn.close()
    for rule in rules:
        prefix = rule['usn_prefix'].upper()
        if usn.startswith(prefix):
            try:
                num = int(usn[len(prefix):])
                if rule['usn_from'] <= num <= rule['usn_to']:
                    return rule['dept'], rule['section']
            except ValueError:
                continue
    return None, None


# ── Routes ─────────────────────────────────────────────────────────────────────

@timetable_bp.route('/')
def timetable_index():
    init_db()
    role = session.get('role')
    uid  = session.get('id', '')

    if role == 'student':
        dept, section = resolve_student_section(uid)
        conn = get_db()
        if dept and section:
            rows = conn.execute(
                "SELECT * FROM Timetables WHERE dept=? AND section=? AND target_type='student' ORDER BY uploaded_at DESC",
                (dept, section)
            ).fetchall()
            label = f"{dept} – Section {section}"
        else:
            rows = conn.execute(
                "SELECT * FROM Timetables WHERE target_type='common' ORDER BY uploaded_at DESC"
            ).fetchall()
            label = "Common Timetable"
        conn.close()
        return render_template('timetable.html', rows=rows, view_label=label,
                               student_dept=dept, student_section=section)

    elif role == 'faculty':
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM Timetables WHERE dept='TEACHER' AND section=? AND target_type='teacher' ORDER BY uploaded_at DESC",
            (uid,)
        ).fetchall()
        conn.close()
        return render_template('timetable.html', rows=rows, view_label=f"Timetable for {uid}",
                               student_dept=None, student_section=None)

    elif role == 'admin':
        conn  = get_db()
        rows  = conn.execute("SELECT * FROM Timetables ORDER BY uploaded_at DESC").fetchall()
        rules = conn.execute("SELECT * FROM SectionRules ORDER BY dept, section").fetchall()
        conn.close()
        return render_template('timetable.html', rows=rows, view_label="All Timetables (Admin)",
                               section_rules=rules, student_dept=None, student_section=None)

    return redirect(url_for('auth.login'))


@timetable_bp.route('/upload', methods=['POST'])
def timetable_upload():
    if session.get('role') != 'admin':
        abort(403)

    label       = request.form.get('label', '').strip()
    dept        = request.form.get('dept', '').strip().upper()
    section     = request.form.get('section', '').strip().upper() or None
    target_type = request.form.get('target_type', 'student').strip()
    teacher_id  = request.form.get('teacher_id', '').strip()
    file        = request.files.get('timetable_file')

    if not label or not dept or not file or file.filename == '':
        flash('Please fill all required fields and select a file.', 'error')
        return redirect(url_for('timetable.timetable_index'))

    allowed = {'.pdf', '.png', '.jpg', '.jpeg', '.webp'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        flash('Only PDF or image files (PNG/JPG/WEBP) are allowed.', 'error')
        return redirect(url_for('timetable.timetable_index'))

    # For teacher timetables: dept="TEACHER", section=teacher_id
    if target_type == 'teacher':
        dept    = 'TEACHER'
        section = teacher_id if teacher_id else section

    safe_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{dept}_{section or 'common'}_{file.filename.replace(' ', '_')}"
    file.save(os.path.join(TT_UPLOADS, safe_name))

    init_db()
    conn = get_db()
    conn.execute(
        "INSERT INTO Timetables (label, dept, section, target_type, filename, uploader, uploaded_at) VALUES (?,?,?,?,?,?,?)",
        (label, dept, section, target_type, safe_name, session.get('id', 'admin'), datetime.now().strftime('%d %b %Y, %H:%M'))
    )
    conn.commit()
    conn.close()

    flash(f'Timetable "{label}" uploaded successfully.', 'success')
    return redirect(url_for('timetable.timetable_index'))


@timetable_bp.route('/delete/<int:tt_id>', methods=['POST'])
def timetable_delete(tt_id):
    if session.get('role') != 'admin':
        abort(403)
    init_db()
    conn = get_db()
    row = conn.execute("SELECT * FROM Timetables WHERE id=?", (tt_id,)).fetchone()
    if row:
        try:
            os.remove(os.path.join(TT_UPLOADS, row['filename']))
        except FileNotFoundError:
            pass
        conn.execute("DELETE FROM Timetables WHERE id=?", (tt_id,))
        conn.commit()
        flash('Timetable deleted.', 'success')
    conn.close()
    return redirect(url_for('timetable.timetable_index'))


@timetable_bp.route('/view/<int:tt_id>')
def timetable_view(tt_id):
    init_db()
    conn = get_db()
    row = conn.execute("SELECT * FROM Timetables WHERE id=?", (tt_id,)).fetchone()
    conn.close()
    if not row:
        abort(404)
    return send_from_directory(TT_UPLOADS, row['filename'], as_attachment=False)


@timetable_bp.route('/download/<int:tt_id>')
def timetable_download(tt_id):
    init_db()
    conn = get_db()
    row = conn.execute("SELECT * FROM Timetables WHERE id=?", (tt_id,)).fetchone()
    conn.close()
    if not row:
        abort(404)
    return send_from_directory(TT_UPLOADS, row['filename'], as_attachment=True,
                               download_name=row['label'] + os.path.splitext(row['filename'])[1])


@timetable_bp.route('/section-rules/update', methods=['POST'])
def update_section_rules():
    """Admin can add/update section rules."""
    if session.get('role') != 'admin':
        abort(403)

    dept       = request.form.get('dept', '').strip().upper()
    section    = request.form.get('section', '').strip().upper()
    usn_prefix = request.form.get('usn_prefix', '').strip().upper()
    usn_from   = request.form.get('usn_from', '').strip()
    usn_to     = request.form.get('usn_to', '').strip()

    if not all([dept, section, usn_prefix, usn_from, usn_to]):
        flash('All section rule fields are required.', 'error')
        return redirect(url_for('timetable.timetable_index'))

    try:
        usn_from = int(usn_from)
        usn_to   = int(usn_to)
    except ValueError:
        flash('USN range must be numbers.', 'error')
        return redirect(url_for('timetable.timetable_index'))

    init_db()
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM SectionRules WHERE dept=? AND section=?", (dept, section)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE SectionRules SET usn_prefix=?, usn_from=?, usn_to=? WHERE dept=? AND section=?",
            (usn_prefix, usn_from, usn_to, dept, section)
        )
    else:
        conn.execute(
            "INSERT INTO SectionRules (dept, section, usn_prefix, usn_from, usn_to) VALUES (?,?,?,?,?)",
            (dept, section, usn_prefix, usn_from, usn_to)
        )
    conn.commit()
    conn.close()
    flash(f'Section rule updated: {dept} – Section {section} ({usn_prefix}{usn_from:03d} to {usn_prefix}{usn_to:03d})', 'success')
    return redirect(url_for('timetable.timetable_index'))

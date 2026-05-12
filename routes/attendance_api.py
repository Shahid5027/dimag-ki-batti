import sqlite3
import qrcode
from flask import Blueprint, render_template, render_template_string, request, make_response, current_app, session, redirect, url_for, flash
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import base64
from io import BytesIO, StringIO
import csv
import uuid
import os

attendance_bp = Blueprint('attendance', __name__)

qr_expiry_seconds = 5
active_tokens = {}

if os.environ.get('VERCEL'):
    DB_PATH = '/tmp/attendance.db'
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'attendance.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            usn TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS Devices (
            device_id TEXT PRIMARY KEY,
            usn TEXT NOT NULL,
            FOREIGN KEY (usn) REFERENCES Users (usn)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS Attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usn TEXT NOT NULL,
            session TEXT NOT NULL,
            status TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usn) REFERENCES Users (usn)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS Leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id TEXT NOT NULL,
            leave_date TEXT NOT NULL,
            leave_type TEXT NOT NULL DEFAULT 'regular',
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ── Migrate Leaves table to new schema if needed ──────────────
    # Check what columns currently exist
    existing_cols = {row[1] for row in c.execute("PRAGMA table_info(Leaves)").fetchall()}

    needs_migration = 'leave_date' not in existing_cols or 'status' not in existing_cols

    if needs_migration:
        # Backup old data
        try:
            old_rows = c.execute("SELECT * FROM Leaves").fetchall()
            old_col_names = [row[1] for row in c.execute("PRAGMA table_info(Leaves)").fetchall()]
        except Exception:
            old_rows = []
            old_col_names = []

        # Drop and recreate with new schema
        c.execute("DROP TABLE IF EXISTS Leaves")
        c.execute('''
            CREATE TABLE Leaves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id TEXT NOT NULL,
                leave_date TEXT NOT NULL DEFAULT '',
                leave_type TEXT NOT NULL DEFAULT 'regular',
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Restore old data — map old 'date' column to new 'leave_date'
        if old_rows and old_col_names:
            col_map = {name: idx for idx, name in enumerate(old_col_names)}
            for row in old_rows:
                tid = row[col_map.get('teacher_id', 0)] if 'teacher_id' in col_map else ''
                old_date = row[col_map['date']] if 'date' in col_map else ''
                ts = row[col_map['timestamp']] if 'timestamp' in col_map else ''
                if tid:
                    c.execute(
                        "INSERT INTO Leaves (teacher_id, leave_date, leave_type, status, timestamp) VALUES (?, ?, 'regular', 'approved', ?)",
                        (tid, old_date or '', ts)
                    )

    conn.commit()
    conn.close()

# HTML Templates
QR_TEMPLATE = """
<!doctype html>
<html>
<head>
    <title>QR Attendance</title>
    <meta http-equiv="refresh" content="{{ expiry }}">
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
        #countdown { font-size: 20px; font-weight: bold; color: #dc3545; margin-top: 20px; }
        #nextqr { font-size: 16px; color: #888; margin-top: 10px; }
    </style>
</head>
<body>
    <h2>Scan this QR code. Valid for <span id="seconds">{{ expiry }}</span> seconds.</h2>
    <img id="qr-img" src="data:image/png;base64,{{ qr }}">
    <div id="countdown">⏳ QR expires in: {{ expiry }} seconds</div>
    <div id="nextqr"></div>

    <script>
        let timer = {{ expiry }};
        const countdown = document.getElementById('countdown');
        const nextQR = document.getElementById('nextqr');
        const qrImg = document.getElementById('qr-img');
        const secondsSpan = document.getElementById('seconds');

        const interval = setInterval(() => {
            timer--;
            secondsSpan.textContent = timer;

            if (timer > 0) {
                countdown.textContent = `⏳ QR expires in: ${timer} second${timer !== 1 ? 's' : ''}`;
            } else {
                countdown.textContent = "❌ QR Code Expired!";
                qrImg.style.display = "none";
                clearInterval(interval);

                let regen = 5;
                nextQR.textContent = `🔄 Next QR in ${regen} seconds...`;

                const regenInterval = setInterval(() => {
                    regen--;
                    nextQR.textContent = `🔄 Next QR in ${regen} second${regen !== 1 ? 's' : ''}...`;
                    if (regen === 0) {
                        clearInterval(regenInterval);
                        location.reload(); // Auto-refresh the page to load new QR
                    }
                }, 1000);
            }
        }, 1000);
    </script>
    <footer style="margin-top: 40px; font-size: 14px; color: #666;">
        <hr style="width: 60%; border: 0.5px solid #ccc;">
        <div style="margin-top: 10px;">
            Developed by <strong>Team Dimag Ki Batti</strong> | Department of ECE | AMC Engineering College
        </div>
    </footer>

</body>
</html>
"""

LOGIN_TEMPLATE = """
<!doctype html>
<title>Login</title>
<h2>Login to mark attendance</h2>
<form method="post">
  <label>1AM24EC</label><input type="text" name="usn" placeholder="e.g., 143" required><br>
  <label>Password</label><input type="password" name="password" required><br>
  <input type="submit" value="Login">
</form>
<p>{{ msg }}</p>
<p>No account? <a href="/attendance/register">Register here</a></p>
"""

REGISTER_TEMPLATE = """
<!doctype html>
<title>Register</title>
<h2>Create your account</h2>
<form method="post">
  <label>1AM24EC</label><input type="text" name="usn" placeholder="e.g., 143" required><br>
  <label>Password</label><input type="password" name="password" required><br>
  <input type="submit" value="Register">
</form>
<p>{{ msg }}</p>
<p>Already registered? <a href="/attendance/">Login</a></p>
"""

SUCCESS_TEMPLATE = """
<!doctype html>
<title>Success</title>
<h2>{{ message }}</h2>
"""

STUDENT_ATTENDANCE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>My Attendance</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: 'Inter', sans-serif; text-align: center; margin-top: 50px; background-color: #f9f9f9; color: #333; }
        .container { max-width: 600px; margin: 0 auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; text-align: left; }
        th, td { padding: 12px; border-bottom: 1px solid #ddd; }
        th { background-color: #f4f4f4; font-weight: bold; }
        tr:hover { background-color: #f1f1f1; }
        .back-link { display: inline-block; margin-bottom: 20px; text-decoration: none; color: #007bff; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">&larr; Back to Dashboard</a>
        <h2>Attendance Record</h2>
        <p><strong>USN:</strong> {{ usn }}</p>
        <table>
            <thead>
                <tr><th>Session</th><th>Status</th><th>Date & Time</th></tr>
            </thead>
            <tbody>
                {% for row in rows %}
                <tr>
                    <td>{{ row['session'] }}</td>
                    <td style="color: green; font-weight: bold;">{{ row['status'] }}</td>
                    <td>{{ row['timestamp'] }}</td>
                </tr>
                {% else %}
                <tr><td colspan="3" style="text-align: center;">No attendance records found.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

# Utility Functions
def generate_qr_token():
    token = str(uuid.uuid4())
    active_tokens[token] = datetime.utcnow()
    return token

def cleanup_tokens():
    now = datetime.utcnow()
    for token in list(active_tokens.keys()):
        if now - active_tokens[token] > timedelta(seconds=qr_expiry_seconds):
            del active_tokens[token]

def get_device_id(req):
    device_id = req.cookies.get("device_id")
    if not device_id:
        device_id = str(uuid.uuid4())
    return device_id

def get_current_session():
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    current_time = now_ist.time()

    schedule = [
        ("09:15", "10:10", "1st Hour"),
        ("10:10", "11:05", "2nd Hour"),
        ("11:05", "11:20", "Short Break"),
        ("11:20", "12:15", "3rd Hour"),
        ("12:15", "13:10", "4th Hour"),
        ("13:10", "14:00", "Lunch Break"),
        ("14:00", "14:55", "5th Hour"),
        ("14:55", "15:50", "6th Hour"),
        ("15:50", "16:45", "7th Hour")
    ]

    for start, end, label in schedule:
        if datetime.strptime(start, "%H:%M").time() <= current_time < datetime.strptime(end, "%H:%M").time():
            return label

    return "⚠️ Not within any class hour."

# Flask Routes
@attendance_bp.route("/")
def qr_page():
    if session.get('role') == 'student':
        init_db()
        conn = get_db()
        c = conn.cursor()
        usn = session.get('id', '').upper()
        c.execute('SELECT * FROM Attendance WHERE usn = ? ORDER BY timestamp DESC', (usn,))
        rows = c.fetchall()
        conn.close()
        return render_template('attendance_student.html', usn=usn, rows=rows)

    if session.get('role') == 'faculty':
        return redirect(url_for('attendance.faculty_report'))

    if session.get('role') not in ['faculty', 'admin']:
        flash("Unauthorized access. Only faculty can generate attendance QRs.")
        return redirect(url_for('index'))

    init_db()
    cleanup_tokens()
    token = generate_qr_token()
    url = f"https://{request.host}/attendance/submit/{token}"
    qr_img = qrcode.make(url)
    buffered = BytesIO()
    qr_img.save(buffered, format="PNG")
    qr_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return render_template('attendance_qr.html', qr=qr_str, expiry=qr_expiry_seconds)


@attendance_bp.route("/generate")
def generate_qr():
    """Explicit QR generation route for faculty/admin (linked from nav)."""
    if session.get('role') not in ['faculty', 'admin']:
        flash("Unauthorized access. Only faculty can generate attendance QRs.")
        return redirect(url_for('index'))

    init_db()
    cleanup_tokens()
    token = generate_qr_token()
    url = f"https://{request.host}/attendance/submit/{token}"
    qr_img = qrcode.make(url)
    buffered = BytesIO()
    qr_img.save(buffered, format="PNG")
    qr_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return render_template('attendance_qr.html', qr=qr_str, expiry=qr_expiry_seconds)


@attendance_bp.route("/submit/<token>", methods=["GET", "POST"])
def submit(token):
    init_db()
    cleanup_tokens()
    if token not in active_tokens:
        return render_template('attendance_success.html', message="❌ QR Code expired or invalid.")

    role = session.get('role')
    if role != 'student':
        return render_template('attendance_success.html', message="❌ Only students can mark attendance.")

    usn = session.get('id', '').upper()
    current_sess = datetime.now().strftime("%d-%m-%Y") + " (" + get_current_session() + ")"

    return mark_attendance(usn, current_sess, "flask_session", token)

@attendance_bp.route("/register", methods=["GET", "POST"])
def register():
    init_db()
    if request.method == "POST":
        suffix = request.form.get("usn").strip().upper()
        password = request.form.get("password").strip()
        usn = f"1AM24EC{suffix}"

        conn = get_db()
        c = conn.cursor()

        c.execute('SELECT usn FROM Users WHERE usn = ?', (usn,))
        if c.fetchone():
            conn.close()
            return render_template('attendance_register.html', msg="⚠️ USN already registered.")

        c.execute('INSERT INTO Users (usn, password) VALUES (?, ?)', (usn, password))
        conn.commit()
        conn.close()
        return render_template('attendance_success.html', message="✅ Registration successful. You can now log in.")

    return render_template('attendance_register.html', msg="")

def mark_attendance(usn, flask_session_label, device_id, token):
    if "⚠️" in flask_session_label or flask_session_label == "No Ongoing Class":
        if token in active_tokens:
            del active_tokens[token]
        return make_response(render_template('attendance_success.html',
            message="❌ Not in class hours. Attendance blocked. Contact your instructor if this is a mistake."
        ))

    conn = get_db()
    c = conn.cursor()

    c.execute('SELECT id FROM Attendance WHERE usn = ? AND session = ? AND status = ?', (usn, flask_session_label, 'P'))
    already_marked = c.fetchone()

    if not already_marked:
        c.execute('INSERT INTO Attendance (usn, session, status) VALUES (?, ?, ?)', (usn, flask_session_label, 'P'))
        conn.commit()
        msg = f"✅ {usn} marked Present for {flask_session_label}"
    else:
        msg = f"⚠️ {usn} already marked Present for {flask_session_label}"

    conn.close()

    if token in active_tokens:
        del active_tokens[token]

    resp = make_response(render_template('attendance_success.html', message=msg))
    resp.set_cookie("device_id", device_id, max_age=31536000)
    resp.set_cookie("user_usn", usn, max_age=31536000)
    return resp

@attendance_bp.route("/take_leave", methods=["GET", "POST"])
def take_leave():
    if session.get('role') != 'faculty':
        flash("Unauthorized access. Only faculty can take leave.")
        return redirect(url_for('index'))

    if request.method == "GET":
        # Render the leave form (handled in attendance_faculty.html with today as min date)
        return redirect(url_for('attendance.faculty_report'))

    init_db()
    teacher_id = session.get('id')
    leave_date_str = request.form.get('leave_date', '').strip()
    leave_type = request.form.get('leave_type', 'regular').strip()
    reason = request.form.get('reason', '').strip()

    # ── Validate date ─────────────────────────────────────
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    today_str = now_ist.strftime("%Y-%m-%d")

    if not leave_date_str:
        flash("Please select a leave date.", "error")
        return redirect(url_for('attendance.faculty_report'))

    try:
        leave_date = datetime.strptime(leave_date_str, "%Y-%m-%d")
    except ValueError:
        flash("Invalid date format.", "error")
        return redirect(url_for('attendance.faculty_report'))

    if leave_date_str < today_str:
        flash("❌ Cannot apply for leave on a past date.", "error")
        return redirect(url_for('attendance.faculty_report'))

    # ── Enforce 12-hour / 1-hour rules ────────────────────
    # Build the leave date's midnight (00:00 IST)
    leave_midnight = datetime(
        leave_date.year, leave_date.month, leave_date.day,
        0, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata")
    )
    hours_until = (leave_midnight - now_ist).total_seconds() / 3600

    if leave_type == 'regular':
        if hours_until < 12:
            flash("❌ Regular leave must be applied at least 12 hours in advance. "
                  "Use 'Emergency' leave for urgent requests.", "error")
            return redirect(url_for('attendance.faculty_report'))
    elif leave_type == 'emergency':
        if hours_until < 1:
            flash("❌ Emergency leave must be applied at least 1 hour in advance.", "error")
            return redirect(url_for('attendance.faculty_report'))
    else:
        flash("❌ Invalid leave type.", "error")
        return redirect(url_for('attendance.faculty_report'))

    conn = get_db()
    c = conn.cursor()

    # No duplicate leaves for same date
    c.execute('SELECT * FROM Leaves WHERE teacher_id = ? AND leave_date = ?',
              (teacher_id, leave_date_str))
    if c.fetchone():
        conn.close()
        flash("⚠️ You have already applied for leave on this date.", "warning")
        return redirect(url_for('attendance.faculty_report'))

    c.execute(
        'INSERT INTO Leaves (teacher_id, leave_date, leave_type, reason, status) VALUES (?, ?, ?, ?, ?)',
        (teacher_id, leave_date_str, leave_type, reason, 'pending')
    )
    conn.commit()
    conn.close()

    flash(f"✅ Leave request submitted for {leave_date_str}. Awaiting admin approval.", "success")
    return redirect(url_for('attendance.faculty_report'))


@attendance_bp.route("/admin/approve_leave/<int:leave_id>", methods=["POST"])
def approve_leave(leave_id):
    if session.get('role') != 'admin':
        flash("Unauthorized access.", "error")
        return redirect(url_for('index'))

    init_db()
    conn = get_db()
    conn.execute("UPDATE Leaves SET status = 'approved' WHERE id = ?", (leave_id,))
    conn.commit()
    conn.close()
    flash("✅ Leave approved.", "success")
    return redirect(url_for('attendance.admin'))


@attendance_bp.route("/admin/reject_leave/<int:leave_id>", methods=["POST"])
def reject_leave(leave_id):
    if session.get('role') != 'admin':
        flash("Unauthorized access.", "error")
        return redirect(url_for('index'))

    init_db()
    conn = get_db()
    conn.execute("UPDATE Leaves SET status = 'rejected' WHERE id = ?", (leave_id,))
    conn.commit()
    conn.close()
    flash("❌ Leave rejected.", "success")
    return redirect(url_for('attendance.admin'))


@attendance_bp.route("/faculty")
def faculty_report():
    if session.get('role') not in ['faculty', 'admin']:
        flash("Unauthorized access.")
        return redirect(url_for('index'))

    init_db()
    conn = get_db()
    c = conn.cursor()

    # All registered students (from Users)
    try:
        c.execute("SELECT usn FROM Users ORDER BY usn")
        all_users = [r['usn'] for r in c.fetchall()]
    except:
        all_users = []

    # All unique sessions
    c.execute("SELECT session FROM Attendance GROUP BY session ORDER BY MIN(timestamp)")
    sessions = [r['session'] for r in c.fetchall()]
    total_sessions = len(sessions)

    # All attendance records
    c.execute("SELECT usn, session FROM Attendance WHERE status = 'P'")
    att_records = c.fetchall()

    # Build matrix: {usn: {session: 'P' or 'A'}}
    att_matrix = {}
    for usn in all_users:
        att_matrix[usn] = {s: 'A' for s in sessions}

    # Include students who marked attendance but might not be in Users
    for r in att_records:
        usn = r['usn']
        sess = r['session']
        if usn not in att_matrix:
            att_matrix[usn] = {s: 'A' for s in sessions}
        att_matrix[usn][sess] = 'P'

    sorted_usns = sorted(att_matrix.keys())
    unique_students = len(sorted_usns)
    total_present = len(att_records)

    # This teacher's leave history
    teacher_id = session.get('id')
    c.execute("SELECT * FROM Leaves WHERE teacher_id = ? ORDER BY leave_date DESC", (teacher_id,))
    my_leaves = c.fetchall()

    conn.close()

    # Date info for the leave form
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    today_str = now_ist.strftime("%Y-%m-%d")
    today_display = now_ist.strftime("%d/%m/%Y")

    return render_template('attendance_faculty.html',
        teacher_id=session.get('id', 'Faculty'),
        total_sessions=total_sessions,
        total_present=total_present,
        unique_students=unique_students,
        sessions=sessions,
        sorted_usns=sorted_usns,
        att_matrix=att_matrix,
        my_leaves=my_leaves,
        today_str=today_str,
        today_display=today_display
    )

@attendance_bp.route("/faculty/download")
def faculty_download():
    if session.get('role') not in ['faculty', 'admin']:
        flash("Unauthorized access.")
        return redirect(url_for('index'))

    init_db()
    conn = get_db()
    c = conn.cursor()

    try:
        c.execute("SELECT usn FROM Users ORDER BY usn")
        all_users = [r['usn'] for r in c.fetchall()]
    except:
        all_users = []

    c.execute("SELECT session FROM Attendance GROUP BY session ORDER BY MIN(timestamp)")
    sessions = [r['session'] for r in c.fetchall()]

    c.execute("SELECT usn, session FROM Attendance WHERE status = 'P'")
    att_records = c.fetchall()

    att_matrix = {}
    for usn in all_users:
        att_matrix[usn] = {s: 'A' for s in sessions}

    for r in att_records:
        usn = r['usn']
        sess = r['session']
        if usn not in att_matrix:
            att_matrix[usn] = {s: 'A' for s in sessions}
        att_matrix[usn][sess] = 'P'

    sorted_usns = sorted(att_matrix.keys())
    conn.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['USN'] + sessions)
    for usn in sorted_usns:
        row = [usn] + [att_matrix[usn][s] for s in sessions]
        cw.writerow(row)

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=attendance_register.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@attendance_bp.route("/admin")
def admin():
    if session.get('role') != 'admin':
        flash("Unauthorized access.")
        return redirect(url_for('index'))

    init_db()
    conn = get_db()
    c = conn.cursor()

    c.execute('SELECT * FROM Attendance ORDER BY timestamp DESC')
    att_rows = c.fetchall()

    c.execute("""SELECT * FROM Leaves
                 ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END,
                 timestamp DESC""")
    leave_rows = c.fetchall()

    conn.close()
    return render_template('attendance_admin.html', att_rows=att_rows, leave_rows=leave_rows)

@attendance_bp.route("/admin/register_student", methods=["POST"])
def register_student():
    if session.get('role') != 'admin':
        flash("Unauthorized access.", "error")
        return redirect(url_for('index'))

    usn = request.form.get('usn', '').strip().upper()
    password = request.form.get('password', '').strip()

    if usn and password:
        init_db()
        conn = get_db()
        try:
            conn.execute("INSERT OR REPLACE INTO Users (usn, password) VALUES (?, ?)", (usn, password))
            conn.commit()
            flash(f"Student {usn} registered successfully.", "success")
        except Exception as e:
            flash(f"Error registering student: {e}", "error")
        finally:
            conn.close()
    else:
        flash("Please provide both USN and Password.", "error")
        
    return redirect(url_for('attendance.admin'))

@attendance_bp.route("/admin/reset_device", methods=["POST"])
def reset_device():
    if session.get('role') != 'admin':
        flash("Unauthorized access.", "error")
        return redirect(url_for('index'))

    usn = request.form.get('usn', '').strip().upper()

    if usn:
        init_db()
        conn = get_db()
        try:
            conn.execute("DELETE FROM Devices WHERE UPPER(usn) = ?", (usn,))
            conn.commit()
            flash(f"Device binding removed for {usn}. They can now log in from a new device.", "success")
        except Exception as e:
            flash(f"Error resetting device: {e}", "error")
        finally:
            conn.close()
    else:
        flash("Please provide a valid USN.", "error")
        
    return redirect(url_for('attendance.admin'))

from flask import Blueprint, render_template, request, session, redirect, url_for, make_response
from routes.attendance_api import get_db, init_db
import re
import uuid

auth_bp = Blueprint('auth', __name__)

STUDENT_PASSWORD = 'student123'
FACULTY_CREDENTIALS = {
    'faculty@amcec.edu': 'faculty123',
    'teacher': 'teacher123',
    'teacher@amcec.edu': 'teacher123'
}
ADMIN_CREDENTIALS = {'admin@amcec.edu': 'admin123', 'admin': 'admin123'}

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        next_url = request.form.get('next') or request.args.get('next') or url_for('index')

        # Check Admin
        if username in ADMIN_CREDENTIALS and ADMIN_CREDENTIALS[username] == password:
            session['role'] = 'admin'
            session['id'] = username
            session.permanent = True
            return redirect(next_url)
            
        # Check Faculty
        if username in FACULTY_CREDENTIALS and FACULTY_CREDENTIALS[username] == password:
            session['role'] = 'faculty'
            session['id'] = username
            session.permanent = True
            return redirect(next_url)

        # Check Student
        usn_upper = username.upper()
        if re.match(r'^1AM24EC\d{1,3}$', usn_upper) or (username.isdigit() and 1 <= len(username) <= 3):
            if username.isdigit():
                usn_upper = f"1AM24EC{username}"

            init_db()
            conn = get_db()
            user = conn.execute("SELECT * FROM Users WHERE UPPER(usn) = ?", (usn_upper,)).fetchone()

            # ── Device-binding check ─────────────────────────────
            device_id = request.cookies.get("device_id")
            if device_id:
                # Is this device already bound to a DIFFERENT student?
                bound = conn.execute(
                    "SELECT usn FROM Devices WHERE device_id = ?", (device_id,)
                ).fetchone()
                if bound and bound['usn'].upper() != usn_upper:
                    conn.close()
                    error = (
                        f"⚠️ This device is already linked to another student account. "
                        f"Contact your Admin to unbind it before logging in."
                    )
                    return render_template('login.html', error=error, next=request.args.get('next'))
            conn.close()

            # Validate credentials
            conn = get_db()
            user = conn.execute("SELECT * FROM Users WHERE UPPER(usn) = ?", (usn_upper,)).fetchone()
            creds_ok = (user and user['password'] == password) or (not user and password == STUDENT_PASSWORD)
            conn.close()

            if creds_ok:
                session['role'] = 'student'
                session['id'] = usn_upper.lower()
                session.permanent = True

                # Bind this device to this student if not already bound
                new_device_id = device_id or str(uuid.uuid4())
                init_db()
                conn = get_db()
                existing = conn.execute(
                    "SELECT device_id FROM Devices WHERE usn = ?", (usn_upper,)
                ).fetchone()
                if not existing:
                    conn.execute(
                        "INSERT OR IGNORE INTO Devices (device_id, usn) VALUES (?, ?)",
                        (new_device_id, usn_upper)
                    )
                    conn.commit()
                conn.close()

                resp = make_response(redirect(next_url))
                resp.set_cookie("device_id", new_device_id, max_age=365 * 24 * 3600, httponly=True, samesite='Lax')
                return resp
                
        error = "Invalid credentials. Please verify your login details."
        return render_template('login.html', error=error, next=request.args.get('next'))
        
    return render_template('login.html', next=request.args.get('next'))

@auth_bp.route('/logout')
def logout():
    """Students cannot log out — only admin/faculty are allowed."""
    role = session.get('role')
    if role == 'student':
        # Block student logout
        return render_template('login.html',
            error="⛔ Students cannot log out of this device. "
                  "This policy prevents attendance fraud. Contact your Admin if you need your device unbound.",
            next=None
        )
    session.clear()
    return redirect(url_for('auth.login'))

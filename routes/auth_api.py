from flask import Blueprint, render_template, request, session, redirect, url_for, make_response
from routes.attendance_api import get_db
import re

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
            # Normalize to full USN
            if username.isdigit():
                usn_upper = f"1AM24EC{username}"

            # Check Database first
            conn = get_db()
            user = conn.execute("SELECT * FROM Users WHERE UPPER(usn) = ?", (usn_upper,)).fetchone()
            conn.close()

            if user and user['password'] == password:
                session['role'] = 'student'
                session['id'] = usn_upper.lower()
                session.permanent = True
                return redirect(next_url)
            
            # Legacy fallback if not registered yet
            if not user and password == STUDENT_PASSWORD:
                session['role'] = 'student'
                session['id'] = usn_upper.lower()
                session.permanent = True
                return redirect(next_url)
                
        error = "Invalid credentials. Please verify your login details."
        return render_template('login.html', error=error, next=request.args.get('next'))
        
    return render_template('login.html', next=request.args.get('next'))

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

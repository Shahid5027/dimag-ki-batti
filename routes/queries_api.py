import sqlite3
import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime
from zoneinfo import ZoneInfo

queries_bp = Blueprint('queries', __name__)

if os.environ.get('VERCEL'):
    QUERIES_DB = '/tmp/queries.db'
else:
    QUERIES_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'queries.db')


def get_db():
    conn = sqlite3.connect(QUERIES_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS Queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usn TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'General',
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            upvotes INTEGER DEFAULT 0,
            status TEXT DEFAULT 'open'
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS QueryUpvotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id INTEGER NOT NULL,
            usn TEXT NOT NULL,
            UNIQUE(query_id, usn),
            FOREIGN KEY (query_id) REFERENCES Queries(id)
        )
    ''')
    conn.commit()
    conn.close()


@queries_bp.route('/')
def index():
    init_db()
    conn = get_db()
    sort = request.args.get('sort', 'votes')  # 'votes' or 'time'
    category_filter = request.args.get('category', '')

    query = 'SELECT * FROM Queries WHERE status = "open"'
    params = []
    if category_filter:
        query += ' AND category = ?'
        params.append(category_filter)

    if sort == 'votes':
        query += ' ORDER BY upvotes DESC, timestamp DESC'
    else:
        query += ' ORDER BY timestamp DESC'

    rows = conn.execute(query, params).fetchall()

    # Get categories for filter
    categories = [r['category'] for r in conn.execute(
        'SELECT DISTINCT category FROM Queries WHERE status = "open"').fetchall()]

    # Which queries did current user upvote?
    current_usn = session.get('id', '').upper()
    upvoted_ids = set()
    if current_usn:
        voted = conn.execute(
            'SELECT query_id FROM QueryUpvotes WHERE usn = ?', (current_usn,)).fetchall()
        upvoted_ids = {r['query_id'] for r in voted}

    conn.close()
    return render_template('queries.html',
                           rows=rows,
                           sort=sort,
                           category_filter=category_filter,
                           categories=categories,
                           upvoted_ids=upvoted_ids,
                           current_usn=current_usn)


@queries_bp.route('/submit', methods=['POST'])
def submit():
    if not session.get('role'):
        flash('Please login first.', 'error')
        return redirect(url_for('auth.login'))

    init_db()
    usn = session.get('id', '').upper() or 'UNKNOWN'
    message = request.form.get('message', '').strip()
    category = request.form.get('category', 'General').strip()

    if not message:
        flash('Query cannot be empty.', 'error')
        return redirect(url_for('queries.index'))

    if len(message) > 500:
        flash('Query too long (max 500 characters).', 'error')
        return redirect(url_for('queries.index'))

    now_ist = datetime.now(ZoneInfo("Asia/Kolkata")).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    conn.execute(
        'INSERT INTO Queries (usn, category, message, timestamp) VALUES (?, ?, ?, ?)',
        (usn, category, message, now_ist)
    )
    conn.commit()
    conn.close()

    flash('✅ Your query has been submitted!', 'success')
    return redirect(url_for('queries.index'))


@queries_bp.route('/upvote/<int:query_id>', methods=['POST'])
def upvote(query_id):
    if not session.get('role'):
        return jsonify({'error': 'Unauthorized'}), 401

    init_db()
    usn = session.get('id', '').upper() or 'UNKNOWN'
    conn = get_db()

    # Check if already upvoted
    existing = conn.execute(
        'SELECT id FROM QueryUpvotes WHERE query_id = ? AND usn = ?',
        (query_id, usn)
    ).fetchone()

    if existing:
        # Toggle off — remove upvote
        conn.execute('DELETE FROM QueryUpvotes WHERE query_id = ? AND usn = ?', (query_id, usn))
        conn.execute('UPDATE Queries SET upvotes = MAX(0, upvotes - 1) WHERE id = ?', (query_id,))
        voted = False
    else:
        # Add upvote
        try:
            conn.execute('INSERT INTO QueryUpvotes (query_id, usn) VALUES (?, ?)', (query_id, usn))
            conn.execute('UPDATE Queries SET upvotes = upvotes + 1 WHERE id = ?', (query_id,))
            voted = True
        except sqlite3.IntegrityError:
            voted = True

    conn.commit()
    new_count = conn.execute('SELECT upvotes FROM Queries WHERE id = ?', (query_id,)).fetchone()['upvotes']
    conn.close()

    return jsonify({'upvotes': new_count, 'voted': voted})


@queries_bp.route('/admin/clear/<int:query_id>', methods=['POST'])
def admin_clear(query_id):
    if session.get('role') != 'admin':
        flash('Unauthorized.', 'error')
        return redirect(url_for('queries.index'))

    init_db()
    conn = get_db()
    conn.execute('UPDATE Queries SET status = "resolved" WHERE id = ?', (query_id,))
    conn.commit()
    conn.close()

    flash('✅ Query marked as resolved.', 'success')
    return redirect(url_for('queries.index'))


@queries_bp.route('/admin/clear-all', methods=['POST'])
def admin_clear_all():
    if session.get('role') != 'admin':
        flash('Unauthorized.', 'error')
        return redirect(url_for('queries.index'))

    init_db()
    conn = get_db()
    conn.execute('UPDATE Queries SET status = "resolved" WHERE status = "open"')
    conn.commit()
    conn.close()

    flash('✅ All queries cleared.', 'success')
    return redirect(url_for('queries.index'))

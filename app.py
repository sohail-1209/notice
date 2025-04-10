from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Upload config
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx'}

# Mail config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'channelavatar2000@gmail.com'
app.config['MAIL_PASSWORD'] = 'bqdx ffos fhwr nvwn'
mail = Mail(app)

# DB config
DB_PATH = os.path.join('database', 'notices.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Helpers
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            category TEXT DEFAULT 'General',
            image TEXT,
            is_pinned INTEGER DEFAULT 0,
            attachment TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notice_id INTEGER,
            name TEXT NOT NULL,
            comment TEXT NOT NULL,
            FOREIGN KEY (notice_id) REFERENCES notices(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            roll_no TEXT UNIQUE,
            mobile_no TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Routes
@app.route('/')
def index():
    query = request.args.get('q', '')
    page = int(request.args.get('page', 1))
    per_page = 5
    offset = (page - 1) * per_page

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if query:
        cursor.execute("SELECT COUNT(*) FROM notices WHERE title LIKE ? OR content LIKE ? OR category LIKE ?",
                       (f'%{query}%', f'%{query}%', f'%{query}%'))
    else:
        cursor.execute("SELECT COUNT(*) FROM notices")
    total_notices = cursor.fetchone()[0]
    total_pages = (total_notices + per_page - 1) // per_page

    if query:
        cursor.execute("""
            SELECT * FROM notices 
            WHERE title LIKE ? OR content LIKE ? OR category LIKE ?
            ORDER BY is_pinned DESC, id DESC LIMIT ? OFFSET ?
        """, (f'%{query}%', f'%{query}%', f'%{query}%', per_page, offset))
    else:
        cursor.execute("SELECT * FROM notices ORDER BY is_pinned DESC, id DESC LIMIT ? OFFSET ?", (per_page, offset))

    notices = cursor.fetchall()

    cursor.execute("SELECT notice_id, name, comment, id FROM comments")
    comment_data = cursor.fetchall()
    comments = {}
    for cid, name, comment, comment_id in comment_data:
        comments.setdefault(cid, []).append((name, comment, comment_id))

    conn.close()
    return render_template('index.html', notices=notices, logged_in=session.get('logged_in'), query=query,
                           page=page, total_pages=total_pages, comments=comments, role=session.get('role'))

@app.route('/add', methods=['POST'])
def add_notice():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))

    title = request.form['title']
    content = request.form['content']
    category = request.form.get('category', 'General')
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    image_filename = None
    attachment_filename = None
    is_pinned = 1 if 'is_pinned' in request.form else 0

    if 'image' in request.files:
        file = request.files['image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(upload_path)
            image_filename = unique_filename

    if 'attachment' in request.files:
        file = request.files['attachment']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            attachment_filename = unique_filename

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO notices (title, content, created_at, category, image, is_pinned, attachment) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (title, content, created_at, category, image_filename, is_pinned, attachment_filename))

    cursor.execute("SELECT email FROM subscribers")
    emails = [row[0] for row in cursor.fetchall()]
    print("Sending emails to:", emails)
    conn.commit()
    conn.close()

    if emails:
        with mail.connect() as conn_mail:
            for email in emails:
                message = Message(
                    subject='New Notice Posted!',
                    sender=app.config['MAIL_USERNAME'],
                    recipients=[email],
                    body=f'New notice titled "{title}" has been posted.\n\n{content}'
                )
                conn_mail.send(message)

    return redirect(url_for('admin_dashboard'))

@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form['email']
    print("Trying to subscribe:", email)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO subscribers (email) VALUES (?)", (email,))
        conn.commit()
        print("Subscribed successfully")
    except sqlite3.IntegrityError:
        print("Email already subscribed")
    conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:notice_id>', methods=['GET', 'POST'])
def edit_notice(notice_id):
    if not session.get('logged_in') or session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category = request.form.get('category', 'General')
        is_pinned = 1 if 'is_pinned' in request.form else 0
        image_filename = None
        attachment_filename = None

        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                image_filename = unique_filename

        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4()}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(file_path)
                attachment_filename = unique_filename

        update_query = "UPDATE notices SET title = ?, content = ?, category = ?, is_pinned = ?"
        update_values = [title, content, category, is_pinned]

        if image_filename:
            update_query += ", image = ?"
            update_values.append(image_filename)

        if attachment_filename:
            update_query += ", attachment = ?"
            update_values.append(attachment_filename)

        update_query += " WHERE id = ?"
        update_values.append(notice_id)

        cursor.execute(update_query, update_values)
        conn.commit()
        conn.close()
        return redirect(url_for('admin_dashboard'))
    else:
        cursor.execute("SELECT * FROM notices WHERE id = ?", (notice_id,))
        notice = cursor.fetchone()
        conn.close()
        return render_template('edit.html', notice=notice)

@app.route('/delete/<int:notice_id>')
def delete_notice(notice_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notices WHERE id = ?", (notice_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/comment/<int:notice_id>', methods=['POST'])
def comment(notice_id):
    name = request.form['name']
    comment = request.form['comment']
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO comments (notice_id, name, comment) VALUES (?, ?, ?)",
                   (notice_id, name, comment))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete_comment/<int:comment_id>', methods=['POST'])
def delete_comment(comment_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT password, role FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and user[0] == password:
            if user[1] == 'admin':
                return render_template('login.html', error='Admins must log in through the Admin Login page.')
            session['logged_in'] = True
            session['username'] = username
            session['role'] = user[1]
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    # Hardcoded admin credentials
    ADMIN_USERNAME = 'scetnotice'
    ADMIN_PASSWORD = 'scet@2025'

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check the hardcoded admin credentials
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            session['role'] = 'admin'  # Assuming admin role
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error='Invalid admin credentials')
    
    return render_template('admin_login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form.get('role', 'user')

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                           (username, password, role))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error='Username already exists')
    
    return render_template('register.html')
@app.route('/admin')
def admin_dashboard():
    if not session.get('logged_in') or session.get('role') != 'admin':
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notices ORDER BY is_pinned DESC, id DESC")
    notices = cursor.fetchall()
    conn.close()

    return render_template('admin_dashboard.html', notices=notices, username=session['username'])


if __name__ == '__main__':
    try:
        init_db()
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        app.logger.error(f"Failed to start app: {e}")


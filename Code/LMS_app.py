from flask import Flask, render_template, request, redirect, url_for, session, send_file
from flask_bcrypt import Bcrypt 
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
bcrypt = Bcrypt(app)
app.secret_key = b'22f2000805'
DATABASE = 'LMS.db'

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

def query_db(query, args=(), one=False):
    with app.app_context():
        cur = get_db().execute(query, args)
        rv = cur.fetchall()
        cur.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    with app.app_context():
        db = get_db()
        db.execute(query, args)
        db.commit()

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
           
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/librarian/login', methods=['GET', 'POST'])
def librarian_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        librarian = query_db('SELECT * FROM Librarian WHERE ID = ?', [username], one=True)
        if librarian and librarian['Password'] == password:
            session['user_type'] = 'librarian'
            return redirect(url_for('librarian_dashboard'))
        else:
            error = "Invalid username or password"
            return render_template('librarian_login.html', error=error)
    return render_template('librarian_login.html')

@app.route('/librarian/register', methods=['POST'])
def register_librarian():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        execute_db('INSERT INTO Librarian (ID, Password) VALUES (?, ?)', [username, password])
        return redirect(url_for('librarian_dashboard'))
    return redirect(url_for('librarian_dashboard'))

@app.route('/librarian/dashboard', methods=['GET', 'POST'])
def librarian_dashboard():
    if 'user_type' not in session or session['user_type'] != 'librarian':
        return redirect(url_for('librarian_login'))

    if request.method == 'POST':
        section_name = request.form['section_name']
        description = request.form['description']
        date_created = datetime.now().strftime('%d %m %Y')

        section_folder = os.path.join('Sections', section_name)
        os.makedirs(section_folder, exist_ok=True)

        execute_db('INSERT INTO Section (Name, DateCreated, Description, DirectoryPath) VALUES (?, ?, ?, ?)',
                   [section_name, date_created, description, section_folder])

    sections = query_db('SELECT * FROM Section')
    return render_template('librarian_dashboard.html', title='Librarian Dashboard', sections=sections)

@app.route('/view_books/<int:section_id>')
def view_books(section_id):
    if 'user_type' not in session or session['user_type'] != 'librarian':   
        return redirect(url_for('librarian_login'))
    books = query_db('SELECT * FROM Book WHERE SectionID = ?', [section_id])
    return render_template('section_books.html', title='Books in Section', books=books)

@app.route('/section_books/<int:section_id>', methods=['GET', 'POST'])
def section_books(section_id):
    if 'user_type' not in session or session['user_type'] != 'librarian':
        return redirect(url_for('librarian_login'))

    if request.method == 'POST':
        book_name = request.form['book_name']
        content = request.form['content']
        author = request.form['author']
        date_issued = datetime.now().strftime('%d %m %Y')

        section = query_db('SELECT * FROM Section WHERE ID = ?', [section_id], one=True)
        if section:
            section_folder = section['DirectoryPath']
            
            if not os.path.exists(section_folder):
                os.makedirs(section_folder)

            uploaded_file = request.files['pdf_file']
            if uploaded_file and allowed_file(uploaded_file.filename):
                filename = secure_filename(uploaded_file.filename)
                file_path = os.path.join(section_folder, filename)
                uploaded_file.save(file_path)

                execute_db('INSERT INTO Book (Name, Content, Author, DateIssued, SectionID, FilePath) VALUES (?, ?, ?, ?, ?, ?)',
                           [book_name, content, author, date_issued, section_id, file_path])

    books = query_db('SELECT * FROM Book WHERE SectionID = ?', [section_id])
    return render_template('section_books.html', books=books, section_id=section_id)

@app.route('/section_books_download/<int:book_id>')
def download_pdf(book_id):
    if 'user_type' not in session or session['user_type'] != 'librarian':
        return redirect(url_for('librarian_login'))
    
    book = query_db('SELECT * FROM Book WHERE ID = ?', [book_id], one=True)
    if not book:
        return "Book not found", 404
    
    file_path = book['FilePath']
    if not os.path.isfile(file_path):
        return "File not found", 404
    
    return send_file(file_path, as_attachment=True)

@app.route('/librarian/new')
def new_librarian():
    return render_template('librarian_register.html')

@app.route('/back_to_dashboard')
def back_to_dashboard():
    return redirect(url_for('librarian_dashboard'))

@app.route('/delete_section/<int:section_id>', methods=['POST'])
def delete_section(section_id):
    if 'user_type' not in session or session['user_type'] != 'librarian':
        return redirect(url_for('librarian_login'))
    
    section = query_db('SELECT * FROM Section WHERE ID = ?', [section_id], one=True)
    if section:
        directory_path = section['DirectoryPath']
        execute_db('DELETE FROM Section WHERE ID = ?', [section_id])
        if os.path.exists(directory_path):
            import shutil
            shutil.rmtree(directory_path)
    return redirect(url_for('librarian_dashboard'))

@app.route('/delete_book/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    if 'user_type' not in session or session['user_type'] != 'librarian':
        return redirect(url_for('librarian_login'))

    book = query_db('SELECT * FROM Book WHERE ID = ?', [book_id], one=True)
    if book:
        file_path = book['FilePath']

        if os.path.exists(file_path):
            os.remove(file_path)

    execute_db('DELETE FROM Book WHERE ID = ?', [book_id])
    return redirect(request.referrer)

@app.route('/librarian/process_request', methods=['GET', 'POST'])
def process_request_page():
    if 'user_type' not in session or session['user_type'] != 'librarian':
        return redirect(url_for('librarian_login'))
    
    if request.method == 'POST':
        action = request.form['action']
        book_id = request.form['book_id']
        user_id = request.form['user_id']
        
        if action == 'accept':
            execute_db('UPDATE UserRequest SET IsRequest = 0, IsProcessed = 1 WHERE BookID = ? AND UserID = ?', [book_id, user_id])
            
            execute_db('INSERT INTO UserBook (UserID, BookID, DateIssued) VALUES (?, ?, ?)', [user_id, book_id, datetime.now().strftime('%d %m %Y')])
        elif action == 'reject' or action == 'revoke':
            execute_db('DELETE FROM UserRequest WHERE BookID = ? AND UserID = ?', [book_id, user_id])

    requests = query_db('''
                        SELECT Book.Name AS book_name, User.Username AS requested_by, UserRequest.BookID AS book_id, UserRequest.UserID AS user_id 
                        FROM UserRequest INNER JOIN Book ON UserRequest.BookID = Book.ID 
                        INNER JOIN User ON UserRequest.UserID = User.Username 
                        WHERE UserRequest.IsRequest = 1 AND UserRequest.IsProcessed = 0
                        ''')
    approved_requests = query_db('''
                                 SELECT Book.Name AS book_name, User.Username AS requested_by, UserRequest.BookID AS book_id, UserRequest.UserID AS user_id 
                                 FROM UserRequest INNER JOIN Book ON UserRequest.BookID = Book.ID 
                                 INNER JOIN User ON UserRequest.UserID = User.Username 
                                 WHERE UserRequest.IsRequest = 0 AND UserRequest.IsProcessed = 1
                                 ''')
    
    return render_template('librarian_request_process.html', requests=requests, approved_requests=approved_requests)


@app.route('/librarian/revoke_request/<int:book_id>/<username>', methods=['POST'])
def revoke_request(book_id, username):
    if 'user_type' not in session or session['user_type'] != 'librarian':
        return redirect(url_for('librarian_login'))
    execute_db('UPDATE UserRequest SET IsRequest = 0, IsProcessed = 0 WHERE UserID = ? AND BookID = ?', [username, book_id])
    execute_db('DELETE FROM UserRequest WHERE UserID = ? AND BookID = ?', [username, book_id])
    execute_db('DELETE FROM UserBook WHERE UserID = ? AND BookID = ?', [username, book_id])
    return redirect(url_for('process_request_page'))


@app.route('/logout')
def logout():
    session.pop('user_type', None)
    session.pop('username', None)
    return redirect(url_for('home'))

@app.route('/user/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = query_db('SELECT * FROM User WHERE Username = ?', [username], one=True)
        if user and bcrypt.check_password_hash(user['Password'], password):
            session['user_type'] = 'user'
            session['username'] = username
            return redirect(url_for('user_dashboard'))
        else:
            error = "Invalid username or password"
            return render_template('user_login.html', error=error)
    return render_template('user_login.html')

@app.route('/user/register', methods=['GET', 'POST'])
def register():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            hashed_password = bcrypt.generate_password_hash(password)
            execute_db('INSERT INTO User (Username, Password) VALUES (?, ?)', [username, hashed_password])
            return redirect(url_for('user_login'))
        return render_template('user_register.html')
    
@app.route('/user/dashboard')   
def user_dashboard():
    db = get_db()
    sections = db.execute('SELECT * FROM Section').fetchall()
    db.close()
    return render_template('user_dashboard.html', sections=sections)

@app.route('/user/section_books/<int:section_id>')
def user_section_books(section_id):
    if 'user_type' not in session or session['user_type'] != 'user':
        return redirect(url_for('user_login'))
    
    section = query_db('SELECT * FROM Section WHERE ID = ?', [section_id], one=True)
    books = query_db('SELECT * FROM Book WHERE SectionID = ?', [section_id])
    return render_template('user_section_books.html', section=section, books=books)

@app.route('/user/request_book/<int:book_id>/<username>', methods=['POST'])
def request_book(book_id, username):
    if 'user_type' not in session or session['user_type'] != 'user':
        return redirect(url_for('user_login'))

    current_date = datetime.now().strftime("%d %m %Y")
    execute_db('INSERT INTO UserRequest (UserID, BookID, Date, IsRequest, IsProcessed) VALUES (?, ?, ?, 1, 0)',
               [username, book_id, current_date])
    
    return redirect(url_for('user_dashboard'))

@app.route('/user/my_books/<username>')
def user_my_books(username):
    if 'user_type' not in session or session['user_type'] != 'user':
        return redirect(url_for('user_login'))
    
    user_books = query_db('''
        SELECT Book.ID AS book_id, Book.Name AS book_name
        FROM UserBook 
        INNER JOIN Book ON UserBook.BookID = Book.ID 
        WHERE UserBook.UserID = ?
    ''', [username])

    librarian_approved_requests = query_db('''
        SELECT Book.ID AS book_id, Book.Name AS book_name
        FROM UserRequest
        INNER JOIN Book ON UserRequest.BookID = Book.ID
        WHERE UserRequest.IsRequest = 0 AND UserRequest.IsProcessed = 1 AND UserRequest.UserID = ?
    ''', [username])
    
    return render_template('user_books.html', user_books=user_books, librarian_approved_requests=librarian_approved_requests)

@app.route('/section_books_view/<int:book_id>')
def view_pdf(book_id):
    book = query_db('SELECT * FROM Book WHERE ID = ?', [book_id], one=True)
    if not book:
        return "Book not found", 404
    
    return send_file(book['FilePath'], as_attachment=False)

if __name__ == '__main__':
    app.run(debug=True)
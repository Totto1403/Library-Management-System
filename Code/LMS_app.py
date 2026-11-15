import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_file, abort, jsonify
)
from werkzeug.utils import secure_filename

from models import db, User, Section, Book, BookIssue, Feedback
from database import seed_database, check_and_revoke_expired_books

# Initialize Flask application
app = Flask(__name__)

# Security & App Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'mad1-lms-secure-key-22f2000805')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f"sqlite:///{os.path.join(app.root_path, 'LMS.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB max upload
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads', 'books')
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize SQLAlchemy
db.init_app(app)

# Helper function: validate allowed file extension
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# Request Hook: Automatically revoke expired book loans on each request
@app.before_request
def before_request_hook():
    check_and_revoke_expired_books()


# Context Processor: Inject user and library state across all Jinja2 templates
@app.context_processor
def inject_global_context():
    current_user = None
    if 'user_id' in session:
        current_user = db.session.get(User, session['user_id'])

    pending_requests_count = 0
    if current_user and current_user.is_librarian:
        pending_requests_count = BookIssue.query.filter_by(status='pending').count()

    active_user_quota = 0
    if current_user and not current_user.is_librarian:
        active_user_quota = current_user.active_quota_count

    return {
        'current_user': current_user,
        'pending_requests_count': pending_requests_count,
        'active_user_quota': active_user_quota,
        'now': datetime.now(timezone.utc)
    }


# ==========================================
# AUTHENTICATION & ACCESS CONTROL DECORATORS
# ==========================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def librarian_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Librarian authentication required.", "warning")
            return redirect(url_for('librarian_login'))
        user = db.session.get(User, session['user_id'])
        if not user or not user.is_librarian:
            flash("Access denied. Librarian administrative privileges required.", "danger")
            return redirect(url_for('user_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in with your student account.", "warning")
            return redirect(url_for('user_login'))
        user = db.session.get(User, session['user_id'])
        if not user or user.is_librarian:
            flash("Please use the librarian portal for administrative tasks.", "info")
            return redirect(url_for('librarian_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ==========================================
# PUBLIC & AUTHENTICATION ROUTES
# ==========================================

@app.route('/')
def home():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user:
            return redirect(url_for('librarian_dashboard' if user.is_librarian else 'user_dashboard'))
    
    total_books = Book.query.count()
    total_sections = Section.query.count()
    total_users = User.query.filter_by(role='user').count()
    recent_books = Book.query.order_by(Book.created_at.desc()).limit(4).all()
    sections = Section.query.limit(4).all()
    
    return render_template('index.html',
                           total_books=total_books,
                           total_sections=total_sections,
                           total_users=total_users,
                           recent_books=recent_books,
                           sections=sections)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user:
            return redirect(url_for('librarian_dashboard' if user.is_librarian else 'user_dashboard'))

    active_tab = request.args.get('role', 'user')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        selected_role = request.form.get('role', 'user')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if selected_role == 'librarian' and not user.is_librarian:
                flash("This account does not have librarian privileges. Please use User Login.", "warning")
                return render_template('login.html', active_tab=selected_role)

            session['user_id'] = user.id
            session['username'] = user.username
            session['user_type'] = user.role

            flash(f"Welcome back, {user.full_name}!", "success")
            next_url = request.args.get('next')
            if next_url:
                return redirect(next_url)
            return redirect(url_for('librarian_dashboard' if user.is_librarian else 'user_dashboard'))
        else:
            flash("Invalid username or password. Please try again.", "danger")
            return render_template('login.html', active_tab=selected_role)

    return render_template('login.html', active_tab=active_tab)


@app.route('/librarian/login', methods=['GET', 'POST'])
def librarian_login():
    return redirect(url_for('login', role='librarian'))


@app.route('/user/login', methods=['GET', 'POST'])
def user_login():
    return redirect(url_for('login', role='user'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()

        if not username or not password or not full_name:
            flash("Please fill in all required fields.", "warning")
            return render_template('register.html')

        if password != confirm_password:
            flash("Passwords do not match.", "warning")
            return render_template('register.html')

        if len(password) < 4:
            flash("Password must be at least 4 characters long.", "warning")
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash("Username is already taken. Please choose another.", "danger")
            return render_template('register.html')

        new_user = User(
            username=username,
            full_name=full_name,
            email=email or f"{username}@study.iitm.ac.in",
            role='user'
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully! Please sign in.", "success")
        return redirect(url_for('login', role='user'))

    return render_template('register.html')


@app.route('/user/register', methods=['GET', 'POST'])
def user_register_alias():
    return redirect(url_for('register'))


@app.route('/librarian/register', methods=['GET', 'POST'])
@login_required
def librarian_register():
    # Only existing authenticated librarians can register a new librarian
    user = db.session.get(User, session['user_id'])
    if not user.is_librarian:
        flash("Only authorized librarians can create additional librarian accounts.", "danger")
        return redirect(url_for('librarian_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()

        if not username or not password or not full_name:
            flash("All fields are required.", "warning")
            return render_template('librarian_register.html')

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return render_template('librarian_register.html')

        new_librarian = User(
            username=username,
            full_name=full_name,
            email=email or f"{username}@iitm.ac.in",
            role='librarian'
        )
        new_librarian.set_password(password)
        db.session.add(new_librarian)
        db.session.commit()

        flash(f"Librarian account '{username}' created successfully.", "success")
        return redirect(url_for('librarian_dashboard'))

    return render_template('librarian_register.html')


@app.route('/librarian/new')
@librarian_required
def new_librarian_alias():
    return redirect(url_for('librarian_register'))


@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for('home'))


# ==========================================
# USER FUNCTIONALITIES
# ==========================================

@app.route('/user/dashboard')
@user_required
def user_dashboard():
    user = db.session.get(User, session['user_id'])
    sections = Section.query.all()
    
    # Recently added books
    recent_books = Book.query.order_by(Book.created_at.desc()).limit(6).all()
    
    # Top rated books
    all_books = Book.query.all()
    top_rated_books = sorted(all_books, key=lambda b: (b.average_rating, b.ratings_count), reverse=True)[:6]

    # User's active loans & requests for quick status
    active_issues = BookIssue.query.filter(
        BookIssue.user_id == user.id,
        BookIssue.status.in_(['issued', 'pending'])
    ).all()
    
    active_book_ids = {issue.book_id: issue for issue in active_issues}

    return render_template('user_dashboard.html',
                           user=user,
                           sections=sections,
                           recent_books=recent_books,
                           top_rated_books=top_rated_books,
                           active_book_ids=active_book_ids)


@app.route('/user/section_books/<int:section_id>')
@user_required
def user_section_books(section_id):
    user = db.session.get(User, session['user_id'])
    section = Section.query.get_or_404(section_id)
    books = Book.query.filter_by(section_id=section_id).all()

    active_issues = BookIssue.query.filter(
        BookIssue.user_id == user.id,
        BookIssue.status.in_(['issued', 'pending'])
    ).all()
    user_status_map = {issue.book_id: issue for issue in active_issues}

    return render_template('user_section_books.html',
                           section=section,
                           books=books,
                           user_status_map=user_status_map,
                           user=user)


@app.route('/user/my_books')
@app.route('/user/my_books/<username>')
@user_required
def user_my_books(username=None):
    user = db.session.get(User, session['user_id'])
    
    active_loans = BookIssue.query.filter_by(user_id=user.id, status='issued').order_by(BookIssue.issue_date.desc()).all()
    pending_requests = BookIssue.query.filter_by(user_id=user.id, status='pending').order_by(BookIssue.request_date.desc()).all()
    past_history = BookIssue.query.filter(
        BookIssue.user_id == user.id,
        BookIssue.status.in_(['returned', 'revoked', 'rejected'])
    ).order_by(BookIssue.request_date.desc()).all()

    # Get user's existing ratings to allow quick editing
    user_feedbacks = {fb.book_id: fb for fb in user.feedbacks}

    return render_template('user_books.html',
                           user=user,
                           active_loans=active_loans,
                           pending_requests=pending_requests,
                           past_history=past_history,
                           user_feedbacks=user_feedbacks)


@app.route('/user/request_book/<int:book_id>', methods=['POST'])
@app.route('/user/request_book/<int:book_id>/<username>', methods=['POST'])
@user_required
def request_book(book_id, username=None):
    user = db.session.get(User, session['user_id'])
    book = Book.query.get_or_404(book_id)

    # Policy 1: Maximum 5 e-books limit (active loans + pending requests)
    if not user.can_request_book:
        flash("Quota limit reached! A student can have a maximum of 5 active e-books (issued + pending). Please return an issued book before requesting another.", "danger")
        return redirect(request.referrer or url_for('user_dashboard'))

    # Policy 2: Duplicate request prevention
    existing_active = BookIssue.query.filter(
        BookIssue.user_id == user.id,
        BookIssue.book_id == book.id,
        BookIssue.status.in_(['issued', 'pending'])
    ).first()

    if existing_active:
        if existing_active.status == 'issued':
            flash(f"You already have an active loan for '{book.title}'. You can read it directly from 'My Books'.", "info")
        else:
            flash(f"You already have a pending request for '{book.title}'. Please wait for the librarian to process it.", "warning")
        return redirect(request.referrer or url_for('user_dashboard'))

    # Create new request
    new_request = BookIssue(
        user_id=user.id,
        book_id=book.id,
        status='pending',
        request_date=datetime.now(timezone.utc)
    )
    db.session.add(new_request)
    db.session.commit()

    flash(f"Request for '{book.title}' submitted successfully. Track status under 'My Books'.", "success")
    return redirect(request.referrer or url_for('user_dashboard'))


@app.route('/user/cancel_request/<int:issue_id>', methods=['POST'])
@user_required
def cancel_request(issue_id):
    user = db.session.get(User, session['user_id'])
    issue = BookIssue.query.get_or_404(issue_id)

    if issue.user_id != user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('user_my_books'))

    if issue.status != 'pending':
        flash("Only pending requests can be cancelled.", "warning")
        return redirect(url_for('user_my_books'))

    book_title = issue.book.title
    db.session.delete(issue)
    db.session.commit()

    flash(f"Request for '{book_title}' has been cancelled.", "info")
    return redirect(url_for('user_my_books'))


@app.route('/user/return_book/<int:issue_id>', methods=['POST'])
@user_required
def return_book(issue_id):
    user = db.session.get(User, session['user_id'])
    issue = BookIssue.query.get_or_404(issue_id)

    if issue.user_id != user.id:
        flash("Unauthorized action.", "danger")
        return redirect(url_for('user_my_books'))

    if issue.status != 'issued':
        flash("This book is not currently issued.", "warning")
        return redirect(url_for('user_my_books'))

    issue.status = 'returned'
    issue.return_date = datetime.now(timezone.utc)
    db.session.commit()

    flash(f"'{issue.book.title}' returned successfully! Please leave a rating and feedback below.", "success")
    return redirect(url_for('user_my_books'))


@app.route('/user/feedback/<int:book_id>', methods=['POST'])
@user_required
def submit_feedback(book_id):
    user = db.session.get(User, session['user_id'])
    book = Book.query.get_or_404(book_id)

    rating_str = request.form.get('rating', '5')
    comment = request.form.get('comment', '').strip()

    try:
        rating = max(1, min(5, int(rating_str)))
    except ValueError:
        rating = 5

    feedback = Feedback.query.filter_by(user_id=user.id, book_id=book.id).first()
    if feedback:
        feedback.rating = rating
        feedback.comment = comment
        feedback.created_at = datetime.now(timezone.utc)
        flash(f"Your rating for '{book.title}' has been updated!", "success")
    else:
        feedback = Feedback(
            user_id=user.id,
            book_id=book.id,
            rating=rating,
            comment=comment
        )
        db.session.add(feedback)
        flash(f"Thank you for rating '{book.title}'!", "success")

    db.session.commit()
    return redirect(request.referrer or url_for('user_my_books'))


# ==========================================
# E-BOOK READING & DOWNLOAD (BULLETPROOF ACCESS)
# ==========================================

@app.route('/section_books_view/<int:book_id>')
@app.route('/book/read/<int:book_id>')
@login_required
def view_pdf(book_id):
    user = db.session.get(User, session['user_id'])
    book = Book.query.get_or_404(book_id)

    # Bulletproof Access Verification:
    # Librarians have administrative access to all books.
    # General users MUST have an active (non-expired) 'issued' loan.
    if not user.is_librarian:
        active_loan = BookIssue.query.filter_by(
            user_id=user.id,
            book_id=book.id,
            status='issued'
        ).first()

        if not active_loan or active_loan.is_expired:
            flash("Access denied. You must have an active, valid loan to read this e-book.", "danger")
            return redirect(url_for('user_my_books'))

    # Resolve file path
    file_path = os.path.join(app.root_path, book.file_path) if not os.path.isabs(book.file_path) else book.file_path
    if not os.path.isfile(file_path):
        flash("The requested eBook PDF file is not available on the server.", "danger")
        return redirect(request.referrer or url_for('home'))

    # If format parameter is raw, send raw PDF stream for iframe/embed
    if request.args.get('raw') == 'true':
        return send_file(file_path, mimetype='application/pdf')

    # Otherwise render clean dedicated reader page
    return render_template('reader.html', book=book)


@app.route('/section_books_download/<int:book_id>')
@app.route('/book/download/<int:book_id>')
@login_required
def download_pdf(book_id):
    user = db.session.get(User, session['user_id'])
    book = Book.query.get_or_404(book_id)

    if not user.is_librarian:
        active_loan = BookIssue.query.filter_by(
            user_id=user.id,
            book_id=book.id,
            status='issued'
        ).first()

        if not active_loan or active_loan.is_expired:
            flash("Access denied. You must have an active loan to download this e-book.", "danger")
            return redirect(url_for('user_my_books'))

    file_path = os.path.join(app.root_path, book.file_path) if not os.path.isabs(book.file_path) else book.file_path
    if not os.path.isfile(file_path):
        flash("The requested eBook PDF file was not found.", "danger")
        return redirect(request.referrer or url_for('home'))

    return send_file(file_path, as_attachment=True, download_name=f"{secure_filename(book.title)}.pdf")


# ==========================================
# UNIVERSAL SEARCH & FILTERING
# ==========================================

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    section_id = request.args.get('section_id', type=int)

    books_query = Book.query
    if query:
        search_filter = (
            Book.title.ilike(f"%{query}%") |
            Book.author.ilike(f"%{query}%") |
            Book.content.ilike(f"%{query}%")
        )
        books_query = books_query.filter(search_filter)

    if section_id:
        books_query = books_query.filter(Book.section_id == section_id)

    results = books_query.all()
    sections = Section.query.all()

    user = None
    user_status_map = {}
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user and not user.is_librarian:
            active_issues = BookIssue.query.filter(
                BookIssue.user_id == user.id,
                BookIssue.status.in_(['issued', 'pending'])
            ).all()
            user_status_map = {issue.book_id: issue for issue in active_issues}

    return render_template('search.html',
                           query=query,
                           selected_section_id=section_id,
                           results=results,
                           sections=sections,
                           user_status_map=user_status_map)


# ==========================================
# LIBRARIAN FUNCTIONALITIES & MANAGEMENT
# ==========================================

@app.route('/librarian/dashboard')
@librarian_required
def librarian_dashboard():
    sections = Section.query.order_by(Section.name).all()
    total_books = Book.query.count()
    total_sections = len(sections)
    total_users = User.query.filter_by(role='user').count()
    active_issues_count = BookIssue.query.filter_by(status='issued').count()
    pending_requests_count = BookIssue.query.filter_by(status='pending').count()
    revoked_count = BookIssue.query.filter_by(status='revoked').count()

    # Recent pending requests preview
    recent_requests = BookIssue.query.filter_by(status='pending').order_by(BookIssue.request_date.desc()).limit(5).all()

    # Recent books added
    recent_books = Book.query.order_by(Book.created_at.desc()).limit(5).all()

    return render_template('librarian_dashboard.html',
                           sections=sections,
                           total_books=total_books,
                           total_sections=total_sections,
                           total_users=total_users,
                           active_issues_count=active_issues_count,
                           pending_requests_count=pending_requests_count,
                           revoked_count=revoked_count,
                           recent_requests=recent_requests,
                           recent_books=recent_books)


@app.route('/librarian/section/add', methods=['POST'])
@librarian_required
def add_section():
    section_name = request.form.get('section_name', '').strip()
    description = request.form.get('description', '').strip()
    icon = request.form.get('icon', 'bi-journal-bookmark-fill').strip()

    if not section_name:
        flash("Section name cannot be empty.", "warning")
        return redirect(url_for('librarian_dashboard'))

    existing = Section.query.filter_by(name=section_name).first()
    if existing:
        flash(f"A section named '{section_name}' already exists.", "danger")
        return redirect(url_for('librarian_dashboard'))

    new_sec = Section(name=section_name, description=description, icon=icon)
    db.session.add(new_sec)
    db.session.commit()

    flash(f"Section '{section_name}' created successfully.", "success")
    return redirect(url_for('librarian_dashboard'))


@app.route('/librarian/section/edit/<int:section_id>', methods=['POST'])
@librarian_required
def edit_section(section_id):
    section = Section.query.get_or_404(section_id)
    new_name = request.form.get('section_name', '').strip()
    new_desc = request.form.get('description', '').strip()
    new_icon = request.form.get('icon', section.icon).strip()

    if not new_name:
        flash("Section name cannot be empty.", "warning")
        return redirect(url_for('librarian_dashboard'))

    duplicate = Section.query.filter(Section.name == new_name, Section.id != section.id).first()
    if duplicate:
        flash(f"Another section with the name '{new_name}' already exists.", "danger")
        return redirect(url_for('librarian_dashboard'))

    section.name = new_name
    section.description = new_desc
    section.icon = new_icon
    db.session.commit()

    flash(f"Section '{section.name}' updated successfully.", "success")
    return redirect(url_for('librarian_dashboard'))


@app.route('/delete_section/<int:section_id>', methods=['POST'])
@app.route('/librarian/section/delete/<int:section_id>', methods=['POST'])
@librarian_required
def delete_section(section_id):
    section = Section.query.get_or_404(section_id)
    sec_name = section.name

    # Remove attached PDF files safely
    for book in section.books:
        fp = os.path.join(app.root_path, book.file_path) if not os.path.isabs(book.file_path) else book.file_path
        if os.path.isfile(fp):
            try:
                os.remove(fp)
            except Exception:
                pass

    db.session.delete(section)
    db.session.commit()

    flash(f"Section '{sec_name}' and all associated books deleted.", "info")
    return redirect(url_for('librarian_dashboard'))


@app.route('/section_books/<int:section_id>', methods=['GET', 'POST'])
@app.route('/librarian/section/<int:section_id>/books', methods=['GET', 'POST'])
@librarian_required
def section_books(section_id):
    section = Section.query.get_or_404(section_id)

    if request.method == 'POST':
        book_name = request.form.get('book_name', '').strip()
        author = request.form.get('author', '').strip()
        content = request.form.get('content', '').strip()
        pages = request.form.get('pages', 1, type=int)
        language = request.form.get('language', 'English').strip()
        edition = request.form.get('edition', '1st Edition').strip()

        if not book_name or not author:
            flash("Book title and author are required.", "warning")
            return redirect(url_for('section_books', section_id=section_id))

        if 'pdf_file' not in request.files:
            flash("Please upload a PDF file for the eBook.", "warning")
            return redirect(url_for('section_books', section_id=section_id))

        uploaded_file = request.files['pdf_file']
        if not uploaded_file or not allowed_file(uploaded_file.filename):
            flash("Only PDF format eBooks (.pdf) are permitted.", "danger")
            return redirect(url_for('section_books', section_id=section_id))

        clean_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(uploaded_file.filename)}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], clean_name)
        uploaded_file.save(save_path)

        relative_path = os.path.relpath(save_path, app.root_path)

        new_book = Book(
            title=book_name,
            author=author,
            content=content,
            section_id=section.id,
            file_path=relative_path,
            pages=pages,
            language=language,
            edition=edition
        )
        db.session.add(new_book)
        db.session.commit()

        flash(f"eBook '{book_name}' added to {section.name} successfully.", "success")
        return redirect(url_for('section_books', section_id=section_id))

    books = Book.query.filter_by(section_id=section_id).all()
    all_sections = Section.query.all()
    return render_template('section_books.html', section=section, books=books, all_sections=all_sections)


@app.route('/view_books/<int:section_id>')
@librarian_required
def view_books_alias(section_id):
    return redirect(url_for('section_books', section_id=section_id))


@app.route('/librarian/books/edit/<int:book_id>', methods=['POST'])
@librarian_required
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)

    book.title = request.form.get('book_name', book.title).strip()
    book.author = request.form.get('author', book.author).strip()
    book.content = request.form.get('content', book.content).strip()
    book.pages = request.form.get('pages', book.pages, type=int)
    book.language = request.form.get('language', book.language).strip()
    book.edition = request.form.get('edition', book.edition).strip()

    new_section_id = request.form.get('section_id', type=int)
    if new_section_id and db.session.get(Section, new_section_id):
        book.section_id = new_section_id

    # Optional PDF replacement
    if 'pdf_file' in request.files:
        uploaded_file = request.files['pdf_file']
        if uploaded_file and allowed_file(uploaded_file.filename):
            clean_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(uploaded_file.filename)}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], clean_name)
            uploaded_file.save(save_path)
            book.file_path = os.path.relpath(save_path, app.root_path)

    db.session.commit()
    flash(f"eBook '{book.title}' updated successfully.", "success")
    return redirect(request.referrer or url_for('section_books', section_id=book.section_id))


@app.route('/delete_book/<int:book_id>', methods=['POST'])
@app.route('/librarian/book/delete/<int:book_id>', methods=['POST'])
@librarian_required
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    sec_id = book.section_id
    book_title = book.title

    # Clean up physical file
    fp = os.path.join(app.root_path, book.file_path) if not os.path.isabs(book.file_path) else book.file_path
    if os.path.isfile(fp):
        try:
            os.remove(fp)
        except Exception:
            pass

    db.session.delete(book)
    db.session.commit()

    flash(f"eBook '{book_title}' deleted.", "info")
    return redirect(request.referrer or url_for('section_books', section_id=sec_id))


@app.route('/librarian/process_request', methods=['GET', 'POST'])
@app.route('/librarian/requests', methods=['GET', 'POST'])
@librarian_required
def process_request_page():
    if request.method == 'POST':
        action = request.form.get('action')
        issue_id = request.form.get('issue_id', type=int)

        issue = db.session.get(BookIssue, issue_id) if issue_id else None

        if issue:
            if action == 'accept':
                loan_days = request.form.get('loan_days', 7, type=int)
                issue.status = 'issued'
                issue.issue_date = datetime.now(timezone.utc)
                issue.due_date = datetime.now(timezone.utc) + timedelta(days=loan_days)
                issue.rejection_reason = None
                flash(f"Access granted for '{issue.book.title}' to {issue.user.username} for {loan_days} days.", "success")
            elif action == 'reject':
                reason = request.form.get('reason', 'Request declined by librarian.').strip()
                issue.status = 'rejected'
                issue.rejection_reason = reason
                flash(f"Request for '{issue.book.title}' was rejected.", "warning")
            elif action == 'revoke':
                issue.status = 'revoked'
                issue.return_date = datetime.now(timezone.utc)
                issue.rejection_reason = request.form.get('reason', 'Revoked by Librarian').strip()
                flash(f"Access revoked for '{issue.book.title}' from {issue.user.username}.", "info")
            db.session.commit()
            return redirect(url_for('process_request_page'))

    # Load request queues
    pending_requests = BookIssue.query.filter_by(status='pending').order_by(BookIssue.request_date.desc()).all()
    active_loans = BookIssue.query.filter_by(status='issued').order_by(BookIssue.issue_date.desc()).all()
    completed_history = BookIssue.query.filter(
        BookIssue.status.in_(['returned', 'revoked', 'rejected'])
    ).order_by(BookIssue.return_date.desc()).limit(50).all()

    return render_template('librarian_request_process.html',
                           pending_requests=pending_requests,
                           active_loans=active_loans,
                           completed_history=completed_history)


@app.route('/librarian/requests/batch_approve', methods=['POST'])
@librarian_required
def batch_approve():
    pending = BookIssue.query.filter_by(status='pending').all()
    now = datetime.now(timezone.utc)
    approved_count = 0
    for issue in pending:
        if issue.user.active_quota_count < 5:
            issue.status = 'issued'
            issue.issue_date = now
            issue.due_date = now + timedelta(days=7)
            approved_count += 1
    db.session.commit()
    flash(f"Batch approved {approved_count} pending requests (7-day loan granted).", "success")
    return redirect(url_for('process_request_page'))


@app.route('/librarian/revoke_request/<int:book_id>/<username>', methods=['POST'])
@librarian_required
def revoke_request_alias(book_id, username):
    user = User.query.filter_by(username=username).first_or_404()
    issue = BookIssue.query.filter_by(user_id=user.id, book_id=book_id, status='issued').first()
    if issue:
        issue.status = 'revoked'
        issue.return_date = datetime.now(timezone.utc)
        issue.rejection_reason = 'Revoked by Librarian'
        db.session.commit()
        flash(f"Revoked '{issue.book.title}' access from {username}.", "info")
    return redirect(url_for('process_request_page'))


@app.route('/librarian/users')
@librarian_required
def librarian_users():
    users = User.query.filter_by(role='user').order_by(User.username).all()
    return render_template('librarian_users.html', users=users)


@app.route('/back_to_dashboard')
def back_to_dashboard():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user and user.is_librarian:
            return redirect(url_for('librarian_dashboard'))
    return redirect(url_for('home'))


# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', code=404, message="The page or resource you requested could not be found."), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('error.html', code=500, message="An internal server error occurred. Please try again."), 500


# Application Startup Hook
with app.app_context():
    seed_database(app)

if __name__ == '__main__':
    app.run(debug=True, port=5000)

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Enforce foreign key constraints on SQLite connections
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # 'user' or 'librarian'
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    issues = db.relationship('BookIssue', backref='user', cascade='all, delete-orphan', lazy=True)
    feedbacks = db.relationship('Feedback', backref='user', cascade='all, delete-orphan', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_librarian(self):
        return self.role == 'librarian'

    @property
    def active_quota_count(self):
        """Count of active books issued or pending request for the 5-book limit."""
        return BookIssue.query.filter(
            BookIssue.user_id == self.id,
            BookIssue.status.in_(['issued', 'pending'])
        ).count()

    @property
    def can_request_book(self):
        return self.active_quota_count < 5

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Section(db.Model):
    __tablename__ = 'sections'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(50), default='bi-journal-bookmark-fill')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    books = db.relationship('Book', backref='section', cascade='all, delete-orphan', lazy=True)

    @property
    def book_count(self):
        return len(self.books)

    def __repr__(self):
        return f"<Section {self.name}>"


class Book(db.Model):
    __tablename__ = 'books'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False, index=True)
    author = db.Column(db.String(150), nullable=False, index=True)
    content = db.Column(db.Text, nullable=True)  # Summary / description
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id', ondelete='CASCADE'), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    pages = db.Column(db.Integer, default=1)
    language = db.Column(db.String(50), default='English')
    edition = db.Column(db.String(50), default='1st Edition')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    issues = db.relationship('BookIssue', backref='book', cascade='all, delete-orphan', lazy=True)
    feedbacks = db.relationship('Feedback', backref='book', cascade='all, delete-orphan', lazy=True)

    @property
    def average_rating(self):
        if not self.feedbacks:
            return 0.0
        return round(sum(f.rating for f in self.feedbacks) / len(self.feedbacks), 1)

    @property
    def ratings_count(self):
        return len(self.feedbacks)

    def get_user_issue(self, user_id):
        """Returns the user's active (issued) or pending issue, if any."""
        return BookIssue.query.filter(
            BookIssue.book_id == self.id,
            BookIssue.user_id == user_id,
            BookIssue.status.in_(['issued', 'pending'])
        ).first()

    def is_issued_to(self, user_id):
        issue = BookIssue.query.filter(
            BookIssue.book_id == self.id,
            BookIssue.user_id == user_id,
            BookIssue.status == 'issued'
        ).first()
        return issue is not None

    def has_pending_request_from(self, user_id):
        issue = BookIssue.query.filter(
            BookIssue.book_id == self.id,
            BookIssue.user_id == user_id,
            BookIssue.status == 'pending'
        ).first()
        return issue is not None

    def active_borrowers_count(self):
        return BookIssue.query.filter(
            BookIssue.book_id == self.id,
            BookIssue.status == 'issued'
        ).count()

    def __repr__(self):
        return f"<Book {self.title} by {self.author}>"


class BookIssue(db.Model):
    __tablename__ = 'book_issues'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Statuses: 'pending', 'issued', 'rejected', 'returned', 'revoked'
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    
    request_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    issue_date = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    return_date = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.String(255), nullable=True)

    @property
    def is_expired(self):
        if self.status == 'issued' and self.due_date:
            now = datetime.now(timezone.utc)
            due = self.due_date if self.due_date.tzinfo else self.due_date.replace(tzinfo=timezone.utc)
            return now > due
        return False

    @property
    def days_remaining(self):
        if self.status == 'issued' and self.due_date:
            now = datetime.now(timezone.utc)
            due = self.due_date if self.due_date.tzinfo else self.due_date.replace(tzinfo=timezone.utc)
            diff = (due - now).total_seconds() / 86400
            return max(0, int(diff))
        return 0

    @property
    def status_badge_class(self):
        mapping = {
            'pending': 'bg-warning text-dark',
            'issued': 'bg-success',
            'returned': 'bg-info text-dark',
            'revoked': 'bg-danger',
            'rejected': 'bg-secondary'
        }
        return mapping.get(self.status, 'bg-secondary')

    def __repr__(self):
        return f"<BookIssue user={self.user_id} book={self.book_id} status={self.status}>"


class Feedback(db.Model):
    __tablename__ = 'feedbacks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.id', ondelete='CASCADE'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1 to 5
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'book_id', name='uq_user_book_feedback'),
    )

    def __repr__(self):
        return f"<Feedback user={self.user_id} book={self.book_id} rating={self.rating}>"

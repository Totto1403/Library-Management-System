import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest
from datetime import datetime, timedelta, timezone
from LMS_app import app, db
from models import User, Section, Book, BookIssue, Feedback
from database import check_and_revoke_expired_books

class LMSTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        self.app = app.test_client()
        with app.app_context():
            db.create_all()
            # Seed test librarian
            admin = User(username='admin', full_name='Librarian Admin', role='librarian')
            admin.set_password('adminpass')
            # Seed test student
            student = User(username='student', full_name='Test Student', role='user')
            student.set_password('studentpass')
            
            # Seed section
            sec = Section(name='CS', description='Computer Science')
            db.session.add_all([admin, student, sec])
            db.session.commit()

            # Seed dummy book
            book = Book(
                title='Test OS Book',
                author='Author X',
                content='Test content',
                section_id=sec.id,
                file_path='uploads/books/operating-systems-intro.pdf'
            )
            db.session.add(book)
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def login(self, username, password, role='user'):
        return self.app.post('/login', data=dict(
            username=username,
            password=password,
            role=role
        ), follow_redirects=True)

    def logout(self):
        return self.app.get('/logout', follow_redirects=True)

    def test_auth_login_success(self):
        rv = self.login('student', 'studentpass', 'user')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'Welcome, Test Student', rv.data)

    def test_auth_login_invalid_password(self):
        rv = self.login('student', 'wrongpassword', 'user')
        self.assertIn(b'Invalid username or password', rv.data)

    def test_auth_librarian_login(self):
        rv = self.login('admin', 'adminpass', 'librarian')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'Librarian Command Center', rv.data)

    def test_student_registration(self):
        rv = self.app.post('/register', data=dict(
            full_name='New Student',
            username='newuser',
            email='new@study.iitm.ac.in',
            password='secretpassword',
            confirm_password='secretpassword'
        ), follow_redirects=True)
        self.assertIn(b'Account created successfully', rv.data)
        with app.app_context():
            u = User.query.filter_by(username='newuser').first()
            self.assertIsNotNone(u)
            self.assertTrue(u.check_password('secretpassword'))

    def test_duplicate_registration_fails(self):
        rv = self.app.post('/register', data=dict(
            full_name='Duplicate Student',
            username='student',
            password='pass',
            confirm_password='pass'
        ), follow_redirects=True)
        self.assertIn(b'already taken', rv.data)

    def test_book_request_and_quota_limit(self):
        self.login('student', 'studentpass')
        with app.app_context():
            b = Book.query.first()
            book_id = b.id

        # 1. Request book
        rv = self.app.post(f'/user/request_book/{book_id}', follow_redirects=True)
        self.assertIn(b'submitted successfully', rv.data)

        # 2. Duplicate request prevention
        rv2 = self.app.post(f'/user/request_book/{book_id}', follow_redirects=True)
        self.assertIn(b'already have a pending request', rv2.data)

        # 3. Simulate 5 requests to test 5-book limit enforcement
        with app.app_context():
            u = User.query.filter_by(username='student').first()
            sec = Section.query.first()
            for i in range(2, 6):
                extra_book = Book(title=f'Book {i}', author='A', content='C', section_id=sec.id, file_path='f.pdf')
                db.session.add(extra_book)
                db.session.flush()
                issue = BookIssue(user_id=u.id, book_id=extra_book.id, status='pending')
                db.session.add(issue)
            db.session.commit()
            
            # Now user has 5 pending requests (quota full)
            self.assertEqual(u.active_quota_count, 5)
            self.assertFalse(u.can_request_book)

            # Add a 6th book to attempt request
            book_6 = Book(title='Book 6', author='A', content='C', section_id=sec.id, file_path='f.pdf')
            db.session.add(book_6)
            db.session.commit()
            b6_id = book_6.id

        # 4. Try requesting 6th book - must fail!
        rv3 = self.app.post(f'/user/request_book/{b6_id}', follow_redirects=True)
        self.assertIn(b'Quota limit reached', rv3.data)

    def test_book_return(self):
        with app.app_context():
            u = User.query.filter_by(username='student').first()
            b = Book.query.first()
            issue = BookIssue(user_id=u.id, book_id=b.id, status='issued', due_date=datetime.now(timezone.utc) + timedelta(days=7))
            db.session.add(issue)
            db.session.commit()
            issue_id = issue.id

        self.login('student', 'studentpass')
        rv = self.app.post(f'/user/return_book/{issue_id}', follow_redirects=True)
        self.assertIn(b'returned successfully', rv.data)

        with app.app_context():
            issue = db.session.get(BookIssue, issue_id)
            self.assertEqual(issue.status, 'returned')
            self.assertIsNotNone(issue.return_date)

    def test_auto_revocation_of_expired_loans(self):
        with app.app_context():
            u = User.query.filter_by(username='student').first()
            b = Book.query.first()
            # Issue book that expired 2 days ago
            past_due = datetime.now(timezone.utc) - timedelta(days=2)
            issue = BookIssue(user_id=u.id, book_id=b.id, status='issued', due_date=past_due)
            db.session.add(issue)
            db.session.commit()
            issue_id = issue.id

            # Trigger auto-revocation logic
            check_and_revoke_expired_books()

            updated_issue = db.session.get(BookIssue, issue_id)
            self.assertEqual(updated_issue.status, 'revoked')
            self.assertIn('expired', updated_issue.rejection_reason)

    def test_feedback_and_average_rating(self):
        with app.app_context():
            b = Book.query.first()
            book_id = b.id

        self.login('student', 'studentpass')
        rv = self.app.post(f'/user/feedback/{book_id}', data=dict(
            rating='5',
            comment='Superb academic text!'
        ), follow_redirects=True)
        self.assertIn(b'Thank you for rating', rv.data)

        with app.app_context():
            b = db.session.get(Book, book_id)
            self.assertEqual(b.average_rating, 5.0)
            self.assertEqual(b.ratings_count, 1)

    def test_librarian_approve_and_revoke(self):
        with app.app_context():
            u = User.query.filter_by(username='student').first()
            b = Book.query.first()
            req = BookIssue(user_id=u.id, book_id=b.id, status='pending')
            db.session.add(req)
            db.session.commit()
            req_id = req.id

        self.login('admin', 'adminpass', 'librarian')
        
        # Approve request with 7 days loan
        rv = self.app.post('/librarian/process_request', data=dict(
            action='accept',
            issue_id=req_id,
            loan_days='7'
        ), follow_redirects=True)
        self.assertIn(b'Access granted', rv.data)

        with app.app_context():
            issue = db.session.get(BookIssue, req_id)
            self.assertEqual(issue.status, 'issued')
            self.assertIsNotNone(issue.due_date)

        # Revoke loan
        rv_revoke = self.app.post('/librarian/process_request', data=dict(
            action='revoke',
            issue_id=req_id
        ), follow_redirects=True)
        self.assertIn(b'Access revoked', rv_revoke.data)

        with app.app_context():
            revoked_issue = db.session.get(BookIssue, req_id)
            self.assertEqual(revoked_issue.status, 'revoked')

    def test_librarian_section_crud(self):
        self.login('admin', 'adminpass', 'librarian')

        # Add section
        rv_add = self.app.post('/librarian/section/add', data=dict(
            section_name='Robotics & AI',
            description='Robotics curriculum',
            icon='bi-cpu-fill'
        ), follow_redirects=True)
        self.assertIn(b'created successfully', rv_add.data)

        with app.app_context():
            sec = Section.query.filter_by(name='Robotics & AI').first()
            self.assertIsNotNone(sec)
            sec_id = sec.id

        # Edit section
        rv_edit = self.app.post(f'/librarian/section/edit/{sec_id}', data=dict(
            section_name='Robotics & Autonomous Systems',
            description='Updated description',
            icon='bi-cpu-fill'
        ), follow_redirects=True)
        self.assertIn(b'updated successfully', rv_edit.data)

        # Delete section
        rv_del = self.app.post(f'/librarian/section/delete/{sec_id}', follow_redirects=True)
        self.assertIn(b'deleted', rv_del.data)

    def test_search_functionality(self):
        rv = self.app.get('/search?q=Test+OS')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'Test OS Book', rv.data)

if __name__ == '__main__':
    unittest.main()

import os
from datetime import datetime, timedelta, timezone
from models import db, User, Section, Book, BookIssue, Feedback

def check_and_revoke_expired_books():
    """
    Core Policy Enforcement:
    Automatically revokes access for books where loan period (e.g., 7 days) has lapsed.
    Runs periodically or on user interactions.
    """
    try:
        now = datetime.now(timezone.utc)
        active_issues = BookIssue.query.filter_by(status='issued').all()
        revoked_count = 0
        for issue in active_issues:
            if issue.due_date:
                due = issue.due_date if issue.due_date.tzinfo else issue.due_date.replace(tzinfo=timezone.utc)
                if now > due:
                    issue.status = 'revoked'
                    issue.return_date = now
                    issue.rejection_reason = 'Loan period expired (7-day automatic revocation policy)'
                    revoked_count += 1
        if revoked_count > 0:
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error checking expired books: {e}")


def seed_database(app):
    """
    Seeds the database with realistic academic library data,
    incorporating real course lecture PDFs and preserving original test credentials.
    """
    with app.app_context():
        db.create_all()

        # 1. Seed Users (with secure password hashing)
        if User.query.count() == 0:
            users_to_seed = [
                {
                    'username': 'librarian',
                    'password': 'password',
                    'role': 'librarian',
                    'full_name': 'Chief Librarian',
                    'email': 'librarian@iitm.ac.in'
                },
                {
                    'username': 'newLibrarian',
                    'password': '#secure1403',
                    'role': 'librarian',
                    'full_name': 'Assistant Librarian',
                    'email': 'admin.library@iitm.ac.in'
                },
                {
                    'username': 'Totto',
                    'password': '1403',
                    'role': 'user',
                    'full_name': 'Totto (22f2000805)',
                    'email': '22f2000805@study.iitm.ac.in'
                },
                {
                    'username': 'student1',
                    'password': 'student123',
                    'role': 'user',
                    'full_name': 'Ananya Sharma',
                    'email': 'ananya.s@study.iitm.ac.in'
                },
                {
                    'username': 'rahul_k',
                    'password': 'password123',
                    'role': 'user',
                    'full_name': 'Rahul Kumar',
                    'email': 'rahul.k@study.iitm.ac.in'
                }
            ]

            for u_data in users_to_seed:
                user = User(
                    username=u_data['username'],
                    role=u_data['role'],
                    full_name=u_data['full_name'],
                    email=u_data['email']
                )
                user.set_password(u_data['password'])
                db.session.add(user)
            db.session.commit()

        # 2. Seed Sections
        if Section.query.count() == 0:
            sections_data = [
                {
                    'name': 'Computer Science & Operating Systems',
                    'description': 'Core computer systems architecture, kernel designs, process scheduling, concurrency, memory management, and system calls.',
                    'icon': 'bi-cpu-fill'
                },
                {
                    'name': 'Software Engineering & Java Programming',
                    'description': 'Object-oriented programming principles, robust design patterns, scalable software development, and enterprise applications.',
                    'icon': 'bi-code-slash'
                },
                {
                    'name': 'Mathematics & Theoretical Foundations',
                    'description': 'Discrete mathematics, linear algebra, probability, queuing models, and computational complexity theory.',
                    'icon': 'bi-calculator-fill'
                },
                {
                    'name': 'Data Science & Modern Application Development',
                    'description': 'Full-stack web architecture, database design, REST APIs, and application lifecycle engineering.',
                    'icon': 'bi-layers-fill'
                }
            ]

            section_objs = {}
            for s_data in sections_data:
                sec = Section(
                    name=s_data['name'],
                    description=s_data['description'],
                    icon=s_data['icon']
                )
                db.session.add(sec)
                db.session.flush()
                section_objs[sec.name] = sec
            db.session.commit()

            # 3. Seed Books using the real lecture PDFs
            books_data = [
                {
                    'title': 'Operating Systems: Foundations & Architecture',
                    'author': 'Dr. Pradeep K V',
                    'content': 'Comprehensive introduction to modern operating systems, hardware virtualization, kernel space vs user space, boot sequences, and essential operating system services.',
                    'section_name': 'Computer Science & Operating Systems',
                    'file_path': 'uploads/books/operating-systems-intro.pdf',
                    'pages': 32,
                    'language': 'English',
                    'edition': '3rd Revised Edition'
                },
                {
                    'title': 'Java Programming & Operating System Principles',
                    'author': 'Dr. Pradeep K V',
                    'content': 'Bridging high-level object-oriented programming in Java with underlying operating system abstractions, multithreaded runtimes, and garbage collection mechanisms.',
                    'section_name': 'Software Engineering & Java Programming',
                    'file_path': 'uploads/books/java-programming-os-principles.pdf',
                    'pages': 32,
                    'language': 'English',
                    'edition': '2nd Edition'
                },
                {
                    'title': 'Operating Systems: Process Scheduling & CPU Algorithms',
                    'author': 'Dr. Pradeep K V',
                    'content': 'In-depth analysis of CPU scheduling algorithms: First-Come-First-Serve (FCFS), Shortest Job First (SJF), Round Robin (RR), Priority Scheduling, and multi-level feedback queues.',
                    'section_name': 'Computer Science & Operating Systems',
                    'file_path': 'uploads/books/os-process-scheduling.pdf',
                    'pages': 77,
                    'language': 'English',
                    'edition': '4th Edition'
                },
                {
                    'title': 'Operating Systems: Concurrency, Locks & Deadlocks',
                    'author': 'Dr. Pradeep K V',
                    'content': 'Advanced treatment of concurrent execution, race conditions, critical section problem, Peterson algorithm, hardware atomic operations, semaphores, monitors, and deadlock avoidance.',
                    'section_name': 'Computer Science & Operating Systems',
                    'file_path': 'uploads/books/os-concurrency-synchronization.pdf',
                    'pages': 45,
                    'language': 'English',
                    'edition': '3rd Edition'
                }
            ]

            book_objs = []
            for b_data in books_data:
                sec = section_objs.get(b_data['section_name'])
                if sec:
                    bk = Book(
                        title=b_data['title'],
                        author=b_data['author'],
                        content=b_data['content'],
                        section_id=sec.id,
                        file_path=b_data['file_path'],
                        pages=b_data['pages'],
                        language=b_data['language'],
                        edition=b_data['edition']
                    )
                    db.session.add(bk)
                    book_objs.append(bk)
            db.session.commit()

            # 4. Seed initial book loans and requests
            totto = User.query.filter_by(username='Totto').first()
            if totto and len(book_objs) >= 4:
                now = datetime.now(timezone.utc)
                # Book 1: Issued to Totto (due in 6 days)
                issue1 = BookIssue(
                    user_id=totto.id,
                    book_id=book_objs[0].id,
                    status='issued',
                    request_date=now - timedelta(days=1),
                    issue_date=now - timedelta(days=1),
                    due_date=now + timedelta(days=6)
                )
                db.session.add(issue1)

                # Book 3: Pending request for Totto
                issue2 = BookIssue(
                    user_id=totto.id,
                    book_id=book_objs[2].id,
                    status='pending',
                    request_date=now - timedelta(hours=2)
                )
                db.session.add(issue2)

                # Book 2: Returned by Totto previously
                issue3 = BookIssue(
                    user_id=totto.id,
                    book_id=book_objs[1].id,
                    status='returned',
                    request_date=now - timedelta(days=10),
                    issue_date=now - timedelta(days=9),
                    due_date=now - timedelta(days=2),
                    return_date=now - timedelta(days=3)
                )
                db.session.add(issue3)

                # Feedbacks
                fb1 = Feedback(
                    user_id=totto.id,
                    book_id=book_objs[0].id,
                    rating=5,
                    comment='Outstanding course notes! The operating system architecture diagrams made kernel concepts crystal clear.'
                )
                fb2 = Feedback(
                    user_id=totto.id,
                    book_id=book_objs[1].id,
                    rating=4,
                    comment='Great insights into Java thread mappings and OS level synchronization primitives.'
                )
                db.session.add_all([fb1, fb2])
                db.session.commit()

            # Add feedback from student1 for Book 3
            student1 = User.query.filter_by(username='student1').first()
            if student1 and len(book_objs) >= 3:
                fb3 = Feedback(
                    user_id=student1.id,
                    book_id=book_objs[2].id,
                    rating=5,
                    comment='The Gantt chart examples for Round Robin and Multi-level feedback queues are the best explanation I have seen.'
                )
                db.session.add(fb3)
                db.session.commit()

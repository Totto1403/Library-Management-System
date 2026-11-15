# IIT Madras - Library Management System (LMS)
## Modern Application Development 1 (MAD 1) Course Project
**Student Roll Number:** 22f2000805  
**Course:** BS in Data Science and Applications, IIT Madras  
**Application Framework:** Flask, Jinja2, Flask-SQLAlchemy (SQLite), Bootstrap 5  

---

## 1. Project Overview

The Library Management System (LMS) is a multi-user digital repository and eBook circulation platform developed for the Modern Application Development 1 (MAD 1) curriculum at IIT Madras. 

The platform addresses manual book tracking, unsynchronized request pipelines, lack of loan expiration policies, and limited accessibility in conventional library software. By combining Flask's routing engine with Flask-SQLAlchemy's relational object-relational mapping (ORM) and a modern Bootstrap 5 responsive interface, the application delivers a resilient, secure, and user-friendly experience for both academic librarians and students.

---

## 2. Key Features and Architectural Upgrades

### Academic Design System and Visual Tokens
- Tailored academic color tokens configured in `:root` (`--surface-base`, `--surface-card`, `--ink-primary`, `--ink-muted`, and `--brand-navy` / `--brand-gold`).
- Standardized tabular numerals (`font-variant-numeric: tabular-nums`) applied across quota counters, remaining loan days, ISBN editions, page lengths, and dates for layout stability.
- Accessible `:focus-visible` focus outlines, custom high-contrast scrollbars, and fluid transition kinetics.
- Replaced generic AI-convergent typefaces with `Public Sans` and `Outfit` for distinguished academic authority and clarity.

### Role-Based Access Control and Authentication
- Secure password hashing using PBKDF2-HMAC-SHA256 via Werkzeug security primitives. Plain-text credentials have been entirely eliminated.
- Single unified user identity schema supporting distinct roles (`user` for students and `librarian` for administrative staff).
- Route protection decorators (`@login_required`, `@librarian_required`, and `@user_required`) that guard against unauthorized access, privilege escalation, and URL tampering.
- Role-specific navigation bars, profile badges, and dynamic flash alert notifications.

### Strict 5-eBook Borrowing Quota and Visual Progress Meter
- Hard enforcement of the mandatory institutional policy: a student can have a maximum of 5 active e-books (active loans plus pending requests).
- Ergonomic 5-segment visual progress meter (`quota-slots-meter`) displaying filled vs. available allocation slots with live status indicators.
- Proactive request prevention: when a student reaches 5 books, request actions are disabled at both the interface level and server-side validation with informative feedback.

### 7-Day Loan Duration and Automated Revocation Engine
- Standard 7-day academic lending window assigned upon librarian approval, with custom durations (7, 14, 21 days) supported via interactive duration pickers.
- High-contrast urgency badges (`Due in X days`, `Due Today`, or `Overdue`) with distinct semantic color states on each borrowed title.
- Automated revocation engine that sweeps active issues and automatically revokes access once a loan exceeds its due date, recording the expiration reason in audit logs.
- Immediate restriction of online reading and downloading for expired or revoked titles.

### eBook Return and Community Feedback System
- Functional book return workflow that updates circulation records, restores student quota capacity, and generates timestamped return receipts.
- Student rating and review system allowing 1 to 5 star ratings and written feedback.
- Real-time computation of average book ratings and review counts displayed across catalogues and dashboard showcases.

### Universal Search and Curriculum Filtering
- Multi-field keyword query matching book titles, authors, and synopsis text.
- Section-based dropdown filtering enabling students to narrow searches by curriculum subject.
- Contextual action buttons reflecting whether a book is available, already borrowed, pending review, or blocked by quota.

### In-Browser eBook Reader and Digital Assets
- Distraction-free, full-height (85vh) reading canvas (`reader.html`) with an integrated top control bar.
- Live remaining loan timer, quick return trigger, digital download link, and full-screen toggle mode.
- Verification of borrowing permissions before serving raw PDF streams or initiating downloads.
- Storage of authentic lecture modules by Dr. Pradeep K V (*Operating Systems Architecture*, *Java and OS Principles*, *CPU Scheduling*, *Concurrency and Synchronization*).

### Administrative Management (Librarian Command Center)
- Executive KPI dashboard displaying real-time metrics with subtle background contrast: Total e-Books, Sections, Active Loans, Pending Requests, Enrolled Students, and Revocations.
- Streamlined Request Processing Pipeline: Triage table with student avatar initials, quota indicators, one-click approvals, custom duration modals (7d/14d/21d), and decline modals with required reason notes.
- Active loans management with immediate administrative revocation capability and detailed circulation audit history.
- Full CRUD operations for Curriculum Sections (Create, Read, Update, Delete with safety checks).
- Full CRUD operations for Books (Upload PDF, Edit Title, Author, Synopsis, Pages, Edition, Language, Reassign Section, Delete).
- Student Activity Monitor tracking individual quota utilization and reading history.

---

## 3. Pre-Seeded Evaluator Accounts

For grading, demonstration, and assessment, the database comes pre-seeded with the following accounts:

| Role | Username | Password | Full Name | Initial State |
| :--- | :--- | :--- | :--- | :--- |
| Student | `Totto` | `1403` | Totto (22f2000805) | 1 active loan, 1 pending request, 1 returned |
| Student | `student1` | `student123` | Ananya Sharma | Quota: 0 / 5 (ready for testing) |
| Student | `rahul_k` | `password123` | Rahul Kumar | Quota: 0 / 5 |
| Librarian | `librarian` | `password` | Chief Librarian | Full administrative access |
| Librarian | `newLibrarian` | `#secure1403` | Senior Librarian | Administrative privileges |

Quick auto-fill buttons are provided on the login page to facilitate evaluation.

---

## 4. How to Run the Application

### Prerequisites
- Python 3.10, 3.11, 3.12, 3.13, or 3.14
- Flask 3.x
- Flask-SQLAlchemy 3.x
- SQLAlchemy 2.x

Dependencies can be installed via:
```powershell
pip install Flask Flask-SQLAlchemy
```

### Launching the Application

#### Method A: From Project Root (Recommended)
```powershell
python run.py
```

#### Method B: From the Code Directory
```powershell
cd Code
python LMS_app.py
```

Once running, navigate to:
```
http://127.0.0.1:5000
```

---

## 5. Automated Testing Suite

The repository contains a unit and integration test suite (`test_lms.py`) containing 12 tests covering all core workflows:
- Student authentication and invalid credential handling
- Librarian authentication and role routing
- Student registration and duplicate username rejection
- Book request creation and duplicate request prevention
- Strict 5-book quota limit enforcement
- Book return processing and quota recovery
- Automated revocation of past-due loans
- Feedback submission and average rating computation
- Librarian approval, loan duration assignment, and manual revocation
- Section CRUD lifecycle
- Search query and filtering operations

Run the test suite via:
```powershell
python Code/test_lms.py
```
Expected output:
```
Ran 12 tests in ~7s
OK
```

---

## 6. Relational Database Architecture

The application uses SQLite via Flask-SQLAlchemy with foreign key constraints enabled (`PRAGMA foreign_keys = ON`).

```
                 +-------------------+
                 |       users       |
                 +-------------------+
                 | id (PK)           |
                 | username (UQ)     |
                 | password_hash     |
                 | role              |
                 | full_name         |
                 | email             |
                 | created_at        |
                 +-------------------+
                   |               |
       1-to-many   |               | 1-to-many
                   v               v
+----------------------+       +----------------------+
|     book_issues      |       |      feedbacks       |
+----------------------+       +----------------------+
| id (PK)              |       | id (PK)              |
| user_id (FK->users)  |       | user_id (FK->users)  |
| book_id (FK->books)  |<-\ /->| book_id (FK->books)  |
| status               |   |   | rating (1..5)        |
| request_date         |   |   | comment              |
| issue_date           |   |   | created_at           |
| due_date             |   |   | UNIQUE(user, book)   |
| return_date          |   |   +----------------------+
| rejection_reason     |   |
+----------------------+   |
                           |
+-------------------+      |
|     sections      |      |
+-------------------+      |
| id (PK)           |      |
| name (UQ)         |      |
| description       |      |
| icon              |      |
| created_at        |      |
+-------------------+      |
         |                 |
1-to-many|                 |
         v                 |
+-------------------+      |
|       books       |      |
+-------------------+      |
| id (PK)           |      |
| title             |      |
| author            |      |
| content           |      |
| section_id (FK)   |      |
| file_path         |------+
| pages             |
| language          |
| edition           |
| created_at        |
+-------------------+
```

---

## 7. Project Directory Layout

```
MAD1 Project / Library-Management-System
|-- run.py                                # Root quick-launch runner
|-- README.md                             # Comprehensive technical documentation
|-- Warning                               # Repository status declaration
|-- Library Management System.txt         # Course problem statement and requirements
|-- LMS Schemas.txt                       # Relational database schema reference
|-- Project_Report_22f2000805.docx        # Comprehensive academic project report
|-- LIbrary_Management.png                # Architecture and database ER diagram
|-- MAD1_Video_Presentation.mp4           # Student project video walkthrough
|
|-- Code / 22f2000805_Project_Folder/Code # Primary Flask application directory
|   |-- LMS_app.py                        # Application entry point, routes, and controllers
|   |-- models.py                         # SQLAlchemy database models and properties
|   |-- database.py                       # Seeding routines and auto-revocation engine
|   |-- test_lms.py                       # 12-test automated unit and integration suite
|   |-- LMS.db                            # SQLite database with pre-seeded data
|   |
|   |-- static/                           # Web assets
|   |   |-- IITM_logo.png                 # Official IIT Madras crest
|   |   `-- style.css                     # Unified modern CSS design system
|   |
|   |-- templates/                        # Jinja2 template views
|   |   |-- base.html                     # Global master template with responsive navbar
|   |   |-- index.html                    # Welcome landing page with showcases and stats
|   |   |-- login.html                    # Unified tabbed sign-in portal with demo auto-fill
|   |   |-- register.html                 # Student registration form
|   |   |-- user_dashboard.html           # Student dashboard with quota tracking
|   |   |-- user_section_books.html       # Section book explorer with borrow controls
|   |   |-- user_books.html               # My Bookshelf: active, pending, history, review
|   |   |-- librarian_dashboard.html      # Administrator KPI dashboard and section CRUD
|   |   |-- section_books.html            # Book management: upload, edit, delete
|   |   |-- librarian_request_process.html# Request approval, custom duration, revocation
|   |   |-- librarian_users.html          # Student activity and quota monitoring
|   |   |-- librarian_register.html       # Administrator account provisioning
|   |   |-- reader.html                   # In-browser PDF document viewer
|   |   |-- search.html                   # Universal search results and filter interface
|   |   `-- error.html                    # Error presentation template (404 / 500)
|   |
|   `-- uploads/                          # Digital eBook storage
|       `-- books/                        # Authentic courseware lecture documents
|           |-- operating-systems-intro.pdf
|           |-- java-programming-os-principles.pdf
|           |-- os-process-scheduling.pdf
|           `-- os-concurrency-synchronization.pdf
|
`-- 22f2000805_Project_Folder/            # Submission bundle for course grading
    |-- Project_Report_22f2000805.pdf     # Academic project report (PDF)
    `-- LMS.zip                           # Complete submission archive
```

---

## 8. Compliance with MAD 1 Problem Statement

| Course Requirement | Implementation Details | Status |
| :--- | :--- | :--- |
| Flask application code | Modular application architecture in `LMS_app.py` with blueprints/context processors. | Complete |
| Jinja2 templates + Bootstrap | Bootstrap 5.3 + custom theme with mobile responsiveness. | Complete |
| SQLite for data storage | Flask-SQLAlchemy with SQLite database file (`LMS.db`). | Complete |
| Multi-user app (Librarian & Users) | Role-Based Access Control (`librarian` and `user`) with secure password hashes. | Complete |
| User can request, read, return | Full request lifecycle with in-browser reader and instant return receipts. | Complete |
| Maximum 5 e-books per user | Enforced on both server-side request handler and interface quota indicators. | Complete |
| Specific loan period (e.g. 7 days) | Default 7-day duration assigned upon approval with live expiration badges. | Complete |
| Automatic revocation after N days | Background engine sweeps expired loans and revokes access automatically. | Complete |
| User feedback and ratings | 1 to 5 star rating system with written comments and dynamic average calculation. | Complete |
| Section and Book Management | Full CRUD operations for sections and books, including file uploads and metadata edits. | Complete |
| Search functionality | Multi-field search across titles, authors, and synopsis with section filters. | Complete |
| Multi-language & UTF-8 support | UTF-8 encoding across database, HTML meta tags, and file handlers. | Complete |
| Local machine execution | Zero external server dependencies; single-command startup via `python run.py`. | Complete |

---
*Developed for IIT Madras BS Degree in Data Science and Applications - Modern Application Development 1.*

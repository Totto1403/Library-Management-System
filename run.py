"""
IIT Madras Modern Application Development 1 (MAD 1)
Library Management System (LMS) - Quick Launch Runner
Student Roll No: 22f2000805
"""

import os
import sys

# Ensure Code directory is in python path and set as working directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CODE_DIR = os.path.join(BASE_DIR, 'Code')
if not os.path.isdir(CODE_DIR):
    CODE_DIR = os.path.join(BASE_DIR, '22f2000805_Project_Folder', 'Code')

if os.path.isdir(CODE_DIR):
    sys.path.insert(0, CODE_DIR)
    os.chdir(CODE_DIR)

from LMS_app import app

def print_banner():
    banner = """
    ===================================================================
              IIT MADRAS - DIGITAL LIBRARY MANAGEMENT SYSTEM
                Course: Modern Application Development 1 (MAD 1)
                Roll Number: 22f2000805 | Student: Totto
    ===================================================================
    [OK] Engine: Flask + Jinja2 + Flask-SQLAlchemy (SQLite)
    [OK] Security: PBKDF2 Password Hashing & Strict RBAC Decorators
    [OK] Quota System: Maximum 5 e-Books per student strictly enforced
    [OK] Policy Engine: 7-Day Loan Duration with Automatic Revocation
    [OK] Review System: 1-5 Star Community Ratings & Student Feedback
    [OK] Media & Files: In-Browser PDF Reader & Digital Downloads
    -------------------------------------------------------------------
    DEMO EVALUATION CREDENTIALS:
      * Student Account 1 : Username: Totto        | Password: 1403
      * Student Account 2 : Username: student1     | Password: student123
      * Chief Librarian   : Username: librarian    | Password: password
      * Senior Librarian  : Username: newLibrarian | Password: #secure1403
    -------------------------------------------------------------------
    Server running at: http://127.0.0.1:5000
    Press Ctrl+C to stop.
    ===================================================================
    """
    print(banner)

if __name__ == '__main__':
    print_banner()
    app.run(debug=True, host='127.0.0.1', port=5000)

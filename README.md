# GREEN SCHOOLS Management System

A beginner-friendly school portal built with Python, Flask, SQLite, HTML, CSS, and JavaScript. It includes role-based dashboards for administrators, teachers, and students.

## Requirements

- Python 3.9 or newer
- Windows PowerShell (the commands below also work in a terminal with small path adjustments)

## Setup on Windows

1. Open PowerShell in the project folder:

   ```powershell
   cd C:\School_management
   ```

2. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, open Command Prompt and run `.venv\Scripts\activate.bat`, or use `.venv\Scripts\python.exe` directly below.

3. Install Flask:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Start the application:

   ```powershell
   python app.py
   ```

5. Open <http://127.0.0.1:5000> in your browser. The SQLite database is created and populated with sample records the first time the app starts.

## Fictional demo accounts

| Role | Username | Password |
| --- | --- | --- |
| Administrator | `admin` | `admin123` |
| Teacher | `teacher` | `teacher123` |
| Student | `student` | `student123` |

All people, school details, and records in the seeded database are fictional. Change these demo passwords before using the application beyond local testing.

## Main features

- Public homepage and student registration
- Login, logout, password hashing, and role-based access
- Student, teacher, and administrator dashboards
- Student directory and attendance recording
- Class timetables and homework
- Marks and results
- Announcements, school events, and holidays
- Form validation, helpful error messages, and responsive layouts
- Public-facing school website with locally served school-campus and mountain-lake photographs

The public homepage uses locally served real photographs so visitors do not need a third-party image request. The illustrative campus image is “Memorial High School New Campus Houston Texas” by Go SMU! (CC BY-SA 4.0); it is not a photograph of the GREEN SCHOOLS campus. The mountain image is “1 lake louise pano 2019” by Chensiyuan (CC BY-SA 4.0). Both source pages and license credits are linked in the website footer.

## Configuration

- `SCHOOL_SECRET_KEY`: set a long random secret key for deployments. Without it, the app uses a random key that changes on each restart (so existing local sessions expire).
- `SCHOOL_DATABASE`: optional path to a SQLite database file.
- `FLASK_DEBUG=1`: enable Flask's development debugger locally only. Debug mode is off by default.

For example, set configuration for the current PowerShell window:

```powershell
$env:SCHOOL_SECRET_KEY = "replace-this-with-a-long-random-value"
python app.py
```

## Run the tests

From the project folder, run:

```powershell
python -m unittest discover -s tests -v
```

The tests use a temporary database and do not modify `school.db`.

## Project structure

```text
School_management/
├── app.py
├── requirements.txt
├── school.db
├── static/
│   ├── app.js
│   └── style.css
└── templates/
    ├── base.html
    ├── home.html
    ├── login.html
    ├── register.html
    ├── students.html
    ├── dashboard.html
    ├── attendance.html
    ├── academics.html
    ├── results.html
    ├── community.html
    └── error.html
```

The database is local to the project and is not intended to be exposed publicly. Use a production WSGI server, HTTPS, a deployment-grade secret key, and stricter operational controls before putting the portal online.

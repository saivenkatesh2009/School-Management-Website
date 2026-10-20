import os
import re
import sqlite3
from datetime import date, datetime
from functools import wraps
from pathlib import Path
from contextlib import contextmanager

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SCHOOL_SECRET_KEY") or os.urandom(32)
app.config["DATABASE"] = os.environ.get("SCHOOL_DATABASE", str(BASE_DIR / "school.db"))


def connect_db():
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def database():
    connection = connect_db()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with database() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'teacher', 'student')),
                display_name TEXT NOT NULL,
                email TEXT UNIQUE
            );
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                roll_number INTEGER NOT NULL UNIQUE,
                user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                attendance_date TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Present', 'Absent', 'Late')),
                UNIQUE(student_id, attendance_date)
            );
            CREATE TABLE IF NOT EXISTS timetable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT NOT NULL,
                weekday TEXT NOT NULL,
                subject TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                teacher TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS homework (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT NOT NULL,
                subject TEXT NOT NULL,
                title TEXT NOT NULL,
                due_date TEXT NOT NULL,
                details TEXT NOT NULL,
                created_by TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS marks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                subject TEXT NOT NULL,
                assessment TEXT NOT NULL,
                score REAL NOT NULL CHECK(score >= 0),
                max_score REAL NOT NULL CHECK(max_score > 0 AND score <= max_score),
                UNIQUE(student_id, subject, assessment)
            );
            CREATE TABLE IF NOT EXISTS announcements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                author TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_date TEXT NOT NULL,
                category TEXT NOT NULL CHECK(category IN ('Event', 'Holiday')),
                details TEXT NOT NULL
            );
            """
        )

        # Retain compatibility with the original students table, which had no user link.
        columns = {row["name"] for row in db.execute("PRAGMA table_info(students)")}
        if "user_id" not in columns:
            db.execute("ALTER TABLE students ADD COLUMN user_id INTEGER REFERENCES users(id)")

        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            existing_students = db.execute(
                "SELECT * FROM students ORDER BY id"
            ).fetchall()
            demo_users = [
                ("admin", "admin123", "admin", "Morgan Ellis", "admin@greenschools.test"),
                ("teacher", "teacher123", "teacher", "Jordan Rivera", "jordan@greenschools.test"),
            ]
            if not existing_students:
                demo_users.append(
                    ("student", "student123", "student", "Casey Morgan", "casey@greenschools.test")
                )
            else:
                demo_users.append(
                    ("student", "student123", "student", existing_students[0]["name"], None)
                )
            user_ids = {}
            for username, password, role, name, email in demo_users:
                cursor = db.execute(
                    "INSERT INTO users (username, password_hash, role, display_name, email) VALUES (?, ?, ?, ?, ?)",
                    (username, generate_password_hash(password), role, name, email),
                )
                user_ids[username] = cursor.lastrowid

            if existing_students:
                primary_student = existing_students[0]
                db.execute(
                    "UPDATE students SET user_id = ? WHERE id = ?",
                    (user_ids["student"], primary_student["id"]),
                )
                casey_id = primary_student["id"]
                sample_class = primary_student["class_name"]
            else:
                db.executemany(
                    "INSERT INTO students (name, class_name, roll_number, user_id) VALUES (?, ?, ?, ?)",
                    [
                        ("Casey Morgan", "Grade 8", 801, user_ids["student"]),
                        ("Avery Bennett", "Grade 8", 802, None),
                        ("Riley Chen", "Grade 7", 703, None),
                    ],
                )
                casey_id = db.execute(
                    "SELECT id FROM students WHERE roll_number = 801"
                ).fetchone()["id"]
                sample_class = "Grade 8"
            db.execute(
                "INSERT INTO attendance (student_id, attendance_date, status) VALUES (?, ?, ?)",
                (casey_id, date.today().isoformat(), "Present"),
            )
            db.executemany(
                "INSERT INTO timetable (class_name, weekday, subject, start_time, end_time, teacher) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (sample_class, "Monday", "Mathematics", "09:00", "09:50", "Jordan Rivera"),
                    (sample_class, "Monday", "Science", "10:10", "11:00", "Taylor Brooks"),
                    (sample_class, "Tuesday", "English", "09:00", "09:50", "Jordan Rivera"),
                ],
            )
            db.execute(
                "INSERT INTO homework (class_name, subject, title, due_date, details, created_by) VALUES (?, ?, ?, ?, ?, ?)",
                (sample_class, "Science", "Plant cell sketch", "2027-01-20", "Label the main parts of a plant cell.", "Jordan Rivera"),
            )
            db.executemany(
                "INSERT INTO marks (student_id, subject, assessment, score, max_score) VALUES (?, ?, ?, ?, ?)",
                [(casey_id, "Mathematics", "Unit 1 quiz", 18, 20), (casey_id, "Science", "Lab report", 27, 30)],
            )
            db.execute(
                "INSERT INTO announcements (title, message, created_at, author) VALUES (?, ?, ?, ?)",
                ("Welcome to GREEN SCHOOLS", "The new school term is underway. Check your dashboard for class updates.", date.today().isoformat(), "Morgan Ellis"),
            )
            db.executemany(
                "INSERT INTO events (title, event_date, category, details) VALUES (?, ?, ?, ?)",
                [
                    ("Community reading morning", "2027-01-22", "Event", "Families are welcome in the library."),
                    ("Winter break", "2027-02-15", "Holiday", "School is closed for the day."),
                ],
            )

        db.execute(
            "UPDATE announcements SET title = ? WHERE title = ? AND message = ? AND author = ?",
            (
                "Welcome to GREEN SCHOOLS",
                "Welcome to ZPH High School",
                "The new school term is underway. Check your dashboard for class updates.",
                "Morgan Ellis",
            ),
        )


def current_user():
    return session.get("user")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Please sign in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user()["role"] not in roles:
                flash("You do not have permission to view that page.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def form_text(field, label, max_length=120):
    value = request.form.get(field, "").strip()
    if not value or len(value) > max_length:
        raise ValueError(f"{label} is required and must be {max_length} characters or fewer.")
    return value


@app.route("/")
def home():
    with database() as db:
        counts = {
            "students": db.execute("SELECT COUNT(*) FROM students").fetchone()[0],
            "teachers": db.execute("SELECT COUNT(*) FROM users WHERE role = 'teacher'").fetchone()[0],
            "announcements": db.execute("SELECT COUNT(*) FROM announcements").fetchone()[0],
        }
        teachers = db.execute(
            "SELECT display_name FROM users WHERE role = 'teacher' ORDER BY display_name"
        ).fetchall()
        announcements = db.execute(
            "SELECT * FROM announcements ORDER BY created_at DESC, id DESC LIMIT 3"
        ).fetchall()
        events = db.execute(
            "SELECT * FROM events WHERE event_date >= ? ORDER BY event_date, id LIMIT 3",
            (date.today().isoformat(),),
        ).fetchall()
    return render_template(
        "home.html", counts=counts, announcements=announcements,
        teachers=teachers, events=events,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with database() as db:
            user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user"] = {
                "id": user["id"],
                "username": user["username"],
                "name": user["display_name"],
                "role": user["role"],
            }
            destination = request.args.get("next")
            if destination and destination.startswith("/") and not destination.startswith("//"):
                return redirect(destination)
            return redirect(url_for("dashboard"))
        flash("The username or password was not recognized.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("home"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            name = form_text("name", "Name")
            class_name = form_text("class_name", "Class", 40)
            username = form_text("username", "Username", 40)
            email = request.form.get("email", "").strip().lower() or None
            password = request.form.get("password", "")
            roll_number = int(request.form.get("roll_number", ""))
            if email and (len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)):
                raise ValueError("Enter a valid email address.")
            if roll_number < 1:
                raise ValueError("Roll number must be a positive number.")
            if len(password) < 8:
                raise ValueError("Password must contain at least 8 characters.")
            with database() as db:
                cursor = db.execute(
                    "INSERT INTO users (username, password_hash, role, display_name, email) VALUES (?, ?, 'student', ?, ?)",
                    (username, generate_password_hash(password), name, email),
                )
                db.execute(
                    "INSERT INTO students (name, class_name, roll_number, user_id) VALUES (?, ?, ?, ?)",
                    (name, class_name, roll_number, cursor.lastrowid),
                )
            flash("Registration complete. You can now sign in.", "success")
            return redirect(url_for("login"))
        except ValueError as error:
            flash(str(error) or "Enter a valid roll number.", "error")
        except sqlite3.IntegrityError:
            flash("That username, email, or roll number is already in use.", "error")
    return render_template("register.html")


@app.route("/dashboard")
@login_required
def dashboard():
    role = current_user()["role"]
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    if role == "teacher":
        return redirect(url_for("teacher_dashboard"))
    return redirect(url_for("student_dashboard"))


@app.route("/dashboard/admin")
@roles_required("admin")
def admin_dashboard():
    with database() as db:
        metrics = {
            "students": db.execute("SELECT COUNT(*) FROM students").fetchone()[0],
            "teachers": db.execute("SELECT COUNT(*) FROM users WHERE role = 'teacher'").fetchone()[0],
            "classes": db.execute("SELECT COUNT(DISTINCT class_name) FROM students").fetchone()[0],
            "present today": db.execute(
                "SELECT COUNT(*) FROM attendance WHERE attendance_date = ? AND status = 'Present'",
                (date.today().isoformat(),),
            ).fetchone()[0],
        }
        students = db.execute("SELECT * FROM students ORDER BY class_name, roll_number LIMIT 6").fetchall()
    return render_template("dashboard.html", title="Admin dashboard", metrics=metrics, students=students)


@app.route("/dashboard/teacher")
@roles_required("teacher")
def teacher_dashboard():
    with database() as db:
        students = db.execute("SELECT * FROM students ORDER BY class_name, roll_number").fetchall()
        homework = db.execute("SELECT * FROM homework ORDER BY due_date LIMIT 5").fetchall()
    return render_template("dashboard.html", title="Teacher dashboard", students=students, homework=homework)


@app.route("/dashboard/student")
@roles_required("student")
def student_dashboard():
    with database() as db:
        student = db.execute(
            "SELECT * FROM students WHERE user_id = ?", (current_user()["id"],)
        ).fetchone()
        if not student:
            flash("Your student profile is not linked. Please contact the school office.", "error")
            return redirect(url_for("home"))
        marks = db.execute("SELECT * FROM marks WHERE student_id = ? ORDER BY id DESC", (student["id"],)).fetchall()
        attendance = db.execute(
            "SELECT * FROM attendance WHERE student_id = ? ORDER BY attendance_date DESC LIMIT 7",
            (student["id"],),
        ).fetchall()
        homework = db.execute(
            "SELECT * FROM homework WHERE class_name = ? ORDER BY due_date LIMIT 5",
            (student["class_name"],),
        ).fetchall()
        timetable = db.execute(
            "SELECT * FROM timetable WHERE class_name = ? ORDER BY weekday, start_time",
            (student["class_name"],),
        ).fetchall()
    return render_template(
        "dashboard.html", title="Student dashboard", student=student, marks=marks,
        attendance=attendance, homework=homework, timetable=timetable,
    )


@app.route("/students", methods=["GET", "POST"])
@roles_required("admin", "teacher")
def students():
    if request.method == "POST":
        flash("Student registrations are created using the secure registration form.", "error")
        return redirect(url_for("register"))
    with database() as db:
        all_students = db.execute("SELECT * FROM students ORDER BY class_name, roll_number").fetchall()
    return render_template("students.html", students=all_students)


@app.route("/attendance", methods=["GET", "POST"])
@roles_required("admin", "teacher")
def attendance():
    with database() as db:
        if request.method == "POST":
            try:
                student_id = int(request.form.get("student_id", ""))
                attendance_date = request.form.get("attendance_date", "")
                status = request.form.get("status", "")
                date.fromisoformat(attendance_date)
                if status not in ("Present", "Absent", "Late"):
                    raise ValueError("Choose a valid attendance status.")
                db.execute(
                    """INSERT INTO attendance (student_id, attendance_date, status) VALUES (?, ?, ?)
                       ON CONFLICT(student_id, attendance_date) DO UPDATE SET status = excluded.status""",
                    (student_id, attendance_date, status),
                )
                flash("Attendance has been saved.", "success")
                return redirect(url_for("attendance"))
            except ValueError:
                flash("Select a student, valid date, and attendance status.", "error")
            except sqlite3.IntegrityError:
                flash("The selected student could not be found.", "error")
        students = db.execute("SELECT * FROM students ORDER BY class_name, roll_number").fetchall()
        records = db.execute(
            """SELECT a.*, s.name, s.class_name, s.roll_number
               FROM attendance a JOIN students s ON s.id = a.student_id
               ORDER BY attendance_date DESC, class_name, roll_number LIMIT 100"""
        ).fetchall()
    return render_template("attendance.html", students=students, records=records, today=date.today().isoformat())


@app.route("/academics", methods=["GET", "POST"])
@login_required
def academics():
    role = current_user()["role"]
    can_manage = role in ("admin", "teacher")
    if request.method == "POST":
        if not can_manage:
            flash("Only teachers and administrators can add academic items.", "error")
            return redirect(url_for("academics"))
        action = request.form.get("action")
        try:
            with database() as db:
                if action == "timetable":
                    weekday = form_text("weekday", "Weekday", 20)
                    start_time = form_text("start_time", "Start time", 5)
                    end_time = form_text("end_time", "End time", 5)
                    start = datetime.strptime(start_time, "%H:%M")
                    end = datetime.strptime(end_time, "%H:%M")
                    if weekday not in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday") or end <= start:
                        raise ValueError("Choose a school weekday and ensure the end time is after the start time.")
                    db.execute(
                        "INSERT INTO timetable (class_name, weekday, subject, start_time, end_time, teacher) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            form_text("class_name", "Class", 40), weekday,
                            form_text("subject", "Subject", 80), start_time,
                            end_time, form_text("teacher", "Teacher", 80),
                        ),
                    )
                elif action == "homework":
                    due_date = request.form.get("due_date", "")
                    date.fromisoformat(due_date)
                    db.execute(
                        "INSERT INTO homework (class_name, subject, title, due_date, details, created_by) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            form_text("class_name", "Class", 40), form_text("subject", "Subject", 80),
                            form_text("title", "Title", 120), due_date,
                            form_text("details", "Details", 1000), current_user()["name"],
                        ),
                    )
                else:
                    raise ValueError("Choose a valid academic item type.")
            flash("The academic item has been added.", "success")
            return redirect(url_for("academics"))
        except ValueError as error:
            flash(str(error) or "Enter a valid date and complete all required fields.", "error")
        except sqlite3.IntegrityError:
            flash("The academic item could not be saved. Check the entered values.", "error")

    with database() as db:
        student = db.execute(
            "SELECT class_name FROM students WHERE user_id = ?", (current_user()["id"],)
        ).fetchone() if role == "student" else None
        class_filter = student["class_name"] if student else None
        timetable_query = "SELECT * FROM timetable"
        homework_query = "SELECT * FROM homework"
        timetable_params = homework_params = ()
        if class_filter:
            timetable_query += " WHERE class_name = ?"
            homework_query += " WHERE class_name = ?"
            timetable_params = homework_params = (class_filter,)
        timetable = db.execute(timetable_query + " ORDER BY weekday, start_time", timetable_params).fetchall()
        homework = db.execute(homework_query + " ORDER BY due_date", homework_params).fetchall()
    return render_template("academics.html", timetable=timetable, homework=homework, can_manage=can_manage)


@app.route("/results", methods=["GET", "POST"])
@login_required
def results():
    role = current_user()["role"]
    can_manage = role in ("admin", "teacher")
    with database() as db:
        if request.method == "POST":
            if not can_manage:
                flash("Only teachers and administrators can record marks.", "error")
                return redirect(url_for("results"))
            try:
                student_id = int(request.form.get("student_id", ""))
                score = float(request.form.get("score", ""))
                max_score = float(request.form.get("max_score", ""))
                if score < 0 or max_score <= 0 or score > max_score:
                    raise ValueError("Score must be between zero and the maximum score.")
                db.execute(
                    """INSERT INTO marks (student_id, subject, assessment, score, max_score)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(student_id, subject, assessment)
                       DO UPDATE SET score = excluded.score, max_score = excluded.max_score""",
                    (student_id, form_text("subject", "Subject", 80), form_text("assessment", "Assessment", 100), score, max_score),
                )
                flash("Result saved successfully.", "success")
                return redirect(url_for("results"))
            except ValueError as error:
                flash(str(error) or "Enter valid marks and select a student.", "error")
            except sqlite3.IntegrityError:
                flash("The selected student could not be found.", "error")

        query = """SELECT m.*, s.name, s.class_name, s.roll_number
                   FROM marks m JOIN students s ON s.id = m.student_id"""
        params = ()
        if role == "student":
            query += " WHERE s.user_id = ?"
            params = (current_user()["id"],)
        marks = db.execute(query + " ORDER BY s.class_name, s.roll_number, m.subject", params).fetchall()
        students = db.execute("SELECT * FROM students ORDER BY class_name, roll_number").fetchall() if can_manage else []
    return render_template("results.html", marks=marks, students=students, can_manage=can_manage)


@app.route("/community", methods=["GET", "POST"])
@login_required
def community():
    can_manage = current_user()["role"] == "admin"
    if request.method == "POST":
        if not can_manage:
            flash("Only administrators can publish announcements and calendar dates.", "error")
            return redirect(url_for("community"))
        try:
            kind = request.form.get("kind")
            with database() as db:
                if kind == "announcement":
                    db.execute(
                        "INSERT INTO announcements (title, message, created_at, author) VALUES (?, ?, ?, ?)",
                        (form_text("title", "Title", 120), form_text("message", "Message", 1000), date.today().isoformat(), current_user()["name"]),
                    )
                elif kind == "calendar":
                    event_date = request.form.get("event_date", "")
                    date.fromisoformat(event_date)
                    category = request.form.get("category")
                    if category not in ("Event", "Holiday"):
                        raise ValueError("Choose Event or Holiday.")
                    db.execute(
                        "INSERT INTO events (title, event_date, category, details) VALUES (?, ?, ?, ?)",
                        (form_text("title", "Title", 120), event_date, category, form_text("details", "Details", 1000)),
                    )
                else:
                    raise ValueError("Choose a valid post type.")
            flash("Your post has been published.", "success")
            return redirect(url_for("community"))
        except ValueError as error:
            flash(str(error) or "Enter a valid date and complete all required fields.", "error")
    with database() as db:
        announcements = db.execute("SELECT * FROM announcements ORDER BY created_at DESC, id DESC").fetchall()
        events = db.execute("SELECT * FROM events ORDER BY event_date, id").fetchall()
    return render_template("community.html", announcements=announcements, events=events, can_manage=can_manage)


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="That page could not be found."), 404


if __name__ == "__main__":
    init_db()
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")

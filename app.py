"""Attendance system and student emotion based engagement prediction - Flask app."""
import glob
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import date
from functools import wraps
from io import BytesIO

from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_file, send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import database as db
import reports

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ID_FOLDER = os.path.join(BASE_DIR, "20170512-110547", "ids")
TMP_DIR = os.path.join(BASE_DIR, "tmp")
os.makedirs(TMP_DIR, exist_ok=True)

ADMIN_USER, ADMIN_PASS = "admin", "admin123"   # static admin credentials
PROJECT_TITLE = "Attendance system and student emotion based engagement prediction"
ATTENDANCE_THRESHOLD = 75

EMOTIONS = ["happy", "surprise", "neutral", "sad", "fear", "angry", "disgust"]
EMOTION_COLORS = {"happy": "#2E9E7A", "surprise": "#3D7EA6", "neutral": "#9AA9AE",
                  "sad": "#6F6AB5", "fear": "#E0A030", "angry": "#D8503F", "disgust": "#8A6D3B"}
# how much each expression says about being engaged with the lecture
EMOTION_WEIGHTS = {"happy": 1.0, "surprise": 0.9, "neutral": 0.7,
                   "fear": 0.35, "angry": 0.3, "disgust": 0.2, "sad": 0.2}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024         # uploads (event images, PDFs) up to 25 MB
EVENT_DIR = os.path.join(BASE_DIR, "static", "uploads", "events")
os.makedirs(EVENT_DIR, exist_ok=True)
IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
MATERIAL_DIR = os.path.join(BASE_DIR, "materials")           # notes / assignment PDFs (not public, served after login)
os.makedirs(MATERIAL_DIR, exist_ok=True)
MATERIAL_KINDS = {"notes": "Notes", "assignment": "Assignment", "quiz": "Quiz"}
INTERNAL1_MAX, INTERNAL2_MAX, ASSIGNMENT_MAX = db.INTERNAL1_MAX, db.INTERNAL2_MAX, db.ASSIGNMENT_MAX
ACTIVITY_MAX, LAB_MAX = db.ACTIVITY_MAX, db.LAB_MAX
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
db.init_db()
db.execute("""CREATE TABLE IF NOT EXISTS attendance_overrides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    faculty_id INTEGER NOT NULL,
    usn TEXT NOT NULL,
    subject TEXT,
    class_date TEXT,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)""")
OVERRIDE_REASONS = {
    "Present": ["Poor lighting", "Camera problem", "Appearance changed (injury, mask, glasses)",
                "Camera could not see the student", "Other (write a note)"],
    "Absent": ["Wrong match (not this student)", "Student left the class",
               "Photo or fake attempt suspected", "Other (write a note)"],
}


# ------------------------------------------------------------------ helpers
@app.context_processor
def inject_globals():
    pending = 0
    if session.get("role") == "faculty":
        pending = len([l for l in leaves_for_faculty(session["faculty_id"]) if l["status"] == "Pending"])
    return dict(pending_leaves=pending, INTERNAL1_MAX=INTERNAL1_MAX, INTERNAL2_MAX=INTERNAL2_MAX, ASSIGNMENT_MAX=ASSIGNMENT_MAX,
                ACTIVITY_MAX=ACTIVITY_MAX, LAB_MAX=LAB_MAX,
                PROJECT_TITLE=PROJECT_TITLE, EMOTIONS=EMOTIONS,
                EMOTION_COLORS=EMOTION_COLORS, THRESHOLD=ATTENDANCE_THRESHOLD,
                departments=db.query("SELECT * FROM departments ORDER BY code"),
                semesters=range(1, 9))


def login_required(role):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if session.get("role") != role:
                flash("Please sign in to continue.", "info")
                return redirect(url_for("login"))
            return fn(*a, **kw)
        return wrapper
    return deco


def run_script(*args):
    """Run dataset.py / recognition.py / monitor.py in a separate process.
    (OpenCV windows need their own main thread, so we never import them into Flask.)"""
    return subprocess.run([sys.executable, *args], cwd=BASE_DIR).returncode


def split_subjects(text):
    return [s.strip() for s in (text or "").split(",") if s.strip()]


def pct(present, total):
    return round(present * 100 / total, 1) if total else None


def engagement_score(counts):
    samples = sum(counts.get(e, 0) for e in EMOTIONS)
    if not samples:
        return 0.0
    return round(sum(EMOTION_WEIGHTS[e] * counts.get(e, 0) for e in EMOTIONS) / samples * 100, 1)


def engagement_level(score):
    if score >= 70:
        return "High"
    if score >= 50:
        return "Moderate"
    return "Low"


def current_faculty():
    return db.query("SELECT * FROM faculty WHERE id = ?", (session["faculty_id"],), one=True)


def slide_list():
    local = []
    for ext in ("jpg", "jpeg", "png", "webp"):
        local += glob.glob(os.path.join(BASE_DIR, "static", "slides", f"*.{ext}"))
    captions = [
        ("Roll call without the roll call", "Walk in, sit down, you are marked present."),
        ("Know how the class is feeling", "Emotion signals turn into an engagement score per student."),
        ("One place for every department", "Faculty and admins see the same attendance record."),
        ("Built on FaceNet and DeepFace", "Face recognition and emotion detection in one pipeline."),
        ("Less admin, more teaching", "Minutes of lecture time back in every class."),
    ]
    fx = ["circle", "slide", "blur", "diag", "zoom"]
    gradients = ["linear-gradient(135deg,#10303A,#2A5F6E)", "linear-gradient(135deg,#1B4552,#3D7EA6)",
                 "linear-gradient(135deg,#143B33,#2E9E7A)", "linear-gradient(135deg,#2A2F5C,#6F6AB5)",
                 "linear-gradient(135deg,#3B2A14,#F2A900)"]
    if local:
        urls = [url_for("static", filename="slides/" + os.path.basename(p)) for p in sorted(local)]
    else:  # remote stock photos; the gradient shows through if they fail to load
        ids = ["1523050854058-8df90110c9f1", "1580582932707-520aed937b7b", "1524178232363-1fb2b075b655",
               "1503676260728-1c00da094a0b", "1509062522246-3755977927d7"]
        urls = [f"https://images.unsplash.com/photo-{i}?auto=format&fit=crop&w=1920&q=70" for i in ids]
    return [dict(url=u, fx=fx[i % len(fx)], fallback=gradients[i % len(gradients)],
                 title=captions[i % len(captions)][0], text=captions[i % len(captions)][1])
            for i, u in enumerate(urls)]


# --------------------------------------------------------------------- public
@app.route("/")
def home():
    faculty = db.query("SELECT * FROM faculty ORDER BY department, username")
    faculty = [dict(f, subject_list=split_subjects(f["subjects"])) for f in faculty]
    dept_counts = db.query("""SELECT d.code, d.name, COUNT(s.usn) AS n FROM departments d
                              LEFT JOIN students s ON s.department = d.code GROUP BY d.code ORDER BY d.code""")
    return render_template("home.html", stats=db.get_stats(), faculty=faculty,
                           dept_counts=dept_counts, slides=slide_list())


@app.route("/login", methods=["GET", "POST"])
def login():
    role = request.form.get("role", request.args.get("role", "faculty"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if role == "admin":
            if username == ADMIN_USER and password == ADMIN_PASS:
                session.clear()
                session["role"], session["name"] = "admin", "Administrator"
                return redirect(url_for("admin_dashboard"))
        elif role == "student":      # username = student name, password = USN
            row = db.query("SELECT * FROM students WHERE lower(name) = lower(?) AND usn = ?",
                           (username, password.strip().upper()), one=True)
            if row:
                session.clear()
                session["role"], session["usn"], session["name"] = "student", row["usn"], row["name"]
                return redirect(url_for("student_dashboard"))
        else:
            row = db.query("SELECT * FROM faculty WHERE username = ?", (username,), one=True)
            if row and check_password_hash(row["password_hash"], password):
                session.clear()
                session["role"], session["faculty_id"] = "faculty", row["id"]
                session["name"] = row["full_name"] or row["username"]
                return redirect(url_for("faculty_dashboard"))
        flash("Username or password is incorrect.", "error")
    return render_template("login.html", role=role)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("home"))


# ---------------------------------------------------------------------- admin
@app.route("/admin")
@login_required("admin")
def admin_dashboard():
    stats = db.get_stats()
    rows = db.student_attendance()
    low = [r for r in rows if r["percent"] is not None and r["percent"] < ATTENDANCE_THRESHOLD]
    sessions = db.query("SELECT COUNT(*) c FROM class_sessions", one=True)["c"]
    monitors = db.query("SELECT COUNT(*) c FROM monitoring_sessions", one=True)["c"]
    by_dept = db.query("""SELECT department, COUNT(*) n FROM students GROUP BY department ORDER BY department""")
    return render_template("admin/dashboard.html", stats=stats, low=low[:8], sessions=sessions,
                           monitors=monitors, by_dept=[dict(r) for r in by_dept])


@app.route("/admin/students", methods=["GET", "POST"])
@login_required("admin")
def admin_students():
    if request.method == "POST":
        usn = request.form.get("usn", "").strip().upper()
        name = request.form.get("name", "").strip()
        semester = request.form.get("semester", type=int)
        department = request.form.get("department", "")
        if not (usn and name and semester and department):
            flash("Fill in USN, name, semester and department.", "error")
        elif db.query("SELECT 1 FROM students WHERE usn = ?", (usn,), one=True):
            flash(f"{usn} is already registered.", "error")
        elif not usn.replace("-", "").isalnum():
            flash("USN can only contain letters, numbers and hyphens.", "error")
        else:
            db.execute("INSERT INTO students (usn, name, semester, department) VALUES (?,?,?,?)",
                       (usn, name, semester, department))
            run_script("dataset.py", usn)                       # opens the camera window
            folder = os.path.join(ID_FOLDER, usn)
            if os.path.isdir(folder) and os.listdir(folder):
                flash(f"{name} ({usn}) registered with {len(os.listdir(folder))} face samples.", "success")
            else:
                db.execute("DELETE FROM students WHERE usn = ?", (usn,))
                flash("No face was captured, so the student was not saved. Try again.", "error")
        return redirect(url_for("admin_students"))
    students = db.query("SELECT * FROM students ORDER BY department, semester, usn")
    items = []
    for s in students:
        folder = os.path.join(ID_FOLDER, s["usn"])
        items.append(dict(s, faces=len(os.listdir(folder)) if os.path.isdir(folder) else 0))
    return render_template("admin/students.html", students=items)


@app.route("/admin/students/<usn>/recapture", methods=["POST"])
@login_required("admin")
def admin_recapture(usn):
    if not db.query("SELECT 1 FROM students WHERE usn = ?", (usn,), one=True):
        abort(404)
    run_script("dataset.py", usn)
    flash(f"Face samples updated for {usn}.", "success")
    return redirect(url_for("admin_students"))


@app.route("/admin/students/<usn>/delete", methods=["POST"])
@login_required("admin")
def admin_delete_student(usn):
    import shutil
    db.execute("DELETE FROM attendance WHERE usn = ?", (usn,))
    db.execute("DELETE FROM emotion_records WHERE usn = ?", (usn,))
    db.execute("DELETE FROM material_students WHERE usn = ?", (usn,))
    db.execute("DELETE FROM students WHERE usn = ?", (usn,))
    shutil.rmtree(os.path.join(ID_FOLDER, usn), ignore_errors=True)
    flash(f"{usn} was removed.", "info")
    return redirect(url_for("admin_students"))


@app.route("/admin/faculty", methods=["GET", "POST"])
@login_required("admin")
def admin_faculty():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        department = request.form.get("department", "")
        allowed = {r["name"] for r in db.query(
            "SELECT name FROM subjects WHERE department IN (?, 'ALL')", (department,))}
        by_lower = {n.lower(): n for n in allowed}
        chosen = [x for x in dict.fromkeys(request.form.getlist("subjects")) if x in allowed]
        # subjects typed by the admin because they are not in the list
        new_subjects, too_long = [], False
        for raw in request.form.getlist("custom_subject"):
            name = " ".join(raw.replace(",", " ").split())          # no commas: subjects are stored comma-separated
            if not name:
                continue
            if len(name) > 80:
                too_long = True
                continue
            name = by_lower.get(name.lower(), name)                  # same name as a listed subject -> use the listed one
            if name in allowed:
                if name not in chosen:
                    chosen.append(name)
            elif name.lower() not in [n.lower() for n in new_subjects]:
                new_subjects.append(name)
        everything = chosen + new_subjects
        subjects = ", ".join(everything)
        if too_long:
            flash("A subject name can be at most 80 characters.", "error")
        elif not (username and password and department and subjects):
            flash("Fill in username, password, department and pick or type at least one subject.", "error")
        elif len(password) < 6:
            flash("Password needs at least 6 characters.", "error")
        elif db.query("SELECT 1 FROM faculty WHERE username = ?", (username,), one=True):
            flash(f"Username '{username}' is taken.", "error")
        else:
            db.execute("""INSERT INTO faculty (username, full_name, password_hash, department, subjects)
                          VALUES (?,?,?,?,?)""",
                       (username, full_name, generate_password_hash(password), department, subjects))
            for name in new_subjects:                               # typed subjects join this department's list
                db.execute("INSERT OR IGNORE INTO subjects (name, department, semester, has_lab) VALUES (?,?,NULL,0)",
                           (name, department))
            # the admin decides which of the subjects have a lab (ticked = lab, not ticked = no lab)
            lab_ticked = set(request.form.getlist("lab_subjects")) | set(request.form.getlist("custom_lab"))
            for name in everything:
                db.execute("UPDATE subjects SET has_lab = ? WHERE name = ? AND department IN (?, 'ALL')",
                           (1 if name in lab_ticked else 0, name, department))
            flash(f"Faculty account '{username}' created.", "success")
        return redirect(url_for("admin_faculty"))
    rows = db.query("SELECT * FROM faculty ORDER BY department, username")
    catalog = db.query("SELECT * FROM subjects ORDER BY department = 'ALL' DESC, department, semester, name")
    return render_template("admin/faculty.html", catalog=catalog,
                           faculty=[dict(r, subject_list=split_subjects(r["subjects"])) for r in rows])


@app.route("/admin/faculty/<int:fid>/delete", methods=["POST"])
@login_required("admin")
def admin_delete_faculty(fid):
    for m in db.query("SELECT id, filename FROM materials WHERE faculty_id = ?", (fid,)):
        remove_material_file(m["filename"])
        db.execute("DELETE FROM material_students WHERE material_id = ?", (m["id"],))
    db.execute("DELETE FROM materials WHERE faculty_id = ?", (fid,))
    db.execute("DELETE FROM faculty WHERE id = ?", (fid,))
    flash("Faculty account removed.", "info")
    return redirect(url_for("admin_faculty"))


@app.route("/admin/attendance")
@login_required("admin")
def admin_attendance():
    department = request.args.get("department", "")
    semester = request.args.get("semester", type=int)
    search = request.args.get("q", "").strip()
    rows = db.student_attendance(department or None, semester, search or None)
    tracked = [r for r in rows if r["percent"] is not None]
    avg = round(sum(r["percent"] for r in tracked) / len(tracked), 1) if tracked else None
    low = len([r for r in tracked if r["percent"] < ATTENDANCE_THRESHOLD])
    return render_template("admin/attendance.html", rows=rows, avg=avg, low=low,
                           f_department=department, f_semester=semester, f_q=search)


@app.route("/admin/attendance/<usn>")
@login_required("admin")
def admin_student_detail(usn):
    student = db.query("SELECT * FROM students WHERE usn = ?", (usn,), one=True)
    if not student:
        abort(404)
    subjects = db.query("""SELECT cs.subject, COUNT(a.id) total, SUM(a.status='P') present
                           FROM attendance a JOIN class_sessions cs ON cs.id = a.session_id
                           WHERE a.usn = ? GROUP BY cs.subject ORDER BY cs.subject""", (usn,))
    subjects = [dict(r, percent=pct(r["present"], r["total"])) for r in subjects]
    history = db.query("""SELECT cs.class_date, cs.subject, a.status FROM attendance a
                          JOIN class_sessions cs ON cs.id = a.session_id
                          WHERE a.usn = ? ORDER BY cs.class_date DESC, cs.id DESC LIMIT 30""", (usn,))
    total = sum(s["total"] for s in subjects)
    present = sum(s["present"] for s in subjects)
    return render_template("admin/student_detail.html", student=student, subjects=subjects,
                           history=history, overall=pct(present, total), total=total, present=present)


# -------------------------------------------------------------------- faculty
@app.route("/faculty")
@login_required("faculty")
def faculty_dashboard():
    fac = current_faculty()
    subjects = split_subjects(fac["subjects"])
    subject = request.args.get("subject") if request.args.get("subject") in subjects else (subjects[0] if subjects else "")

    sessions = db.query("""SELECT cs.id, cs.class_date, cs.department, cs.semester,
                                  COUNT(a.id) total, COALESCE(SUM(a.status='P'),0) present
                           FROM class_sessions cs LEFT JOIN attendance a ON a.session_id = cs.id
                           WHERE cs.faculty_id = ? AND cs.subject = ?
                           GROUP BY cs.id ORDER BY cs.class_date, cs.id""", (fac["id"], subject))
    trend = [dict(label=f'{s["class_date"]} ({s["department"]}-{s["semester"]})',
                  value=pct(s["present"], s["total"]) or 0) for s in sessions]

    students = db.query("""SELECT st.usn, st.name, st.department, st.semester, COUNT(a.id) total,
                                  COALESCE(SUM(a.status='P'),0) present
                           FROM attendance a JOIN class_sessions cs ON cs.id = a.session_id
                           JOIN students st ON st.usn = a.usn
                           WHERE cs.faculty_id = ? AND cs.subject = ?
                           GROUP BY st.usn ORDER BY st.department, st.semester, st.usn""",
                        (fac["id"], subject))
    students = [dict(r, percent=pct(r["present"], r["total"])) for r in students]
    avg = round(sum(s["percent"] for s in students) / len(students), 1) if students else None
    low = [s for s in students if s["percent"] < ATTENDANCE_THRESHOLD]
    bands = {"75% and above": len([s for s in students if s["percent"] >= 75]),
             "60 to 74%": len([s for s in students if 60 <= s["percent"] < 75]),
             "Below 60%": len([s for s in students if s["percent"] < 60])}
    monitors = db.query("""SELECT * FROM monitoring_sessions WHERE faculty_id = ?
                           ORDER BY id DESC LIMIT 5""", (fac["id"],))
    return render_template("faculty/dashboard.html", fac=fac, subjects=subjects, subject=subject,
                           sessions=sessions, trend=trend, students=students, avg=avg, low=low,
                           bands=bands, monitors=monitors)


def class_students(department, semester):
    return db.query("SELECT usn, name FROM students WHERE department = ? AND semester = ? ORDER BY usn",
                    (department, semester))


def read_class_form(fac):
    subject = request.form.get("subject", "")
    department = request.form.get("department", "")
    semester = request.form.get("semester", type=int)
    if subject not in split_subjects(fac["subjects"]) or not department or not semester:
        return None
    return subject, department, semester


@app.route("/faculty/attendance")
@login_required("faculty")
def faculty_attendance():
    fac = current_faculty()
    return render_template("faculty/attendance.html", fac=fac, subjects=split_subjects(fac["subjects"]))


@app.route("/faculty/attendance/start", methods=["POST"])
@login_required("faculty")
def faculty_attendance_start():
    fac = current_faculty()
    form = read_class_form(fac)
    if not form:
        flash("Choose a subject, department and semester.", "error")
        return redirect(url_for("faculty_attendance"))
    subject, department, semester = form
    roster = class_students(department, semester)
    if not roster:
        flash(f"No students are registered in {department}, semester {semester}.", "error")
        return redirect(url_for("faculty_attendance"))

    token = uuid.uuid4().hex
    out = os.path.join(TMP_DIR, f"{token}_rec.json")
    run_script("recognition.py", "--out", out, "--allowed", ",".join(r["usn"] for r in roster))
    recognised = []
    if os.path.exists(out):
        with open(out) as f:
            recognised = json.load(f).get("present", [])
        os.remove(out)
    with open(os.path.join(TMP_DIR, f"{token}.json"), "w") as f:
        json.dump(dict(subject=subject, department=department, semester=semester,
                       present=recognised, faculty_id=fac["id"]), f)
    return redirect(url_for("faculty_attendance_review", token=token))


def load_token(token):
    path = os.path.join(TMP_DIR, f"{token}.json")
    if not token.isalnum() or not os.path.exists(path):
        abort(404)
    with open(path) as f:
        data = json.load(f)
    if data["faculty_id"] != session["faculty_id"]:
        abort(403)
    return path, data


@app.route("/faculty/attendance/review/<token>")
@login_required("faculty")
def faculty_attendance_review(token):
    _, data = load_token(token)
    roster = class_students(data["department"], data["semester"])
    leave_map = {}
    for l in db.query("SELECT usn, from_date, to_date FROM leaves WHERE status = 'Approved'"):
        leave_map.setdefault(l["usn"], []).append([l["from_date"], l["to_date"]])
    return render_template("faculty/attendance_review.html", data=data, token=token, roster=roster,
                           today=date.today().isoformat(), leave_map=leave_map)


@app.route("/faculty/attendance/save/<token>", methods=["POST"])
@login_required("faculty")
def faculty_attendance_save(token):
    path, data = load_token(token)
    roster = class_students(data["department"], data["semester"])
    roster_usns = {r["usn"] for r in roster}
    names = {r["usn"]: r["name"] for r in roster}
    present = set(request.form.getlist("present")) & roster_usns
    class_date = request.form.get("class_date") or date.today().isoformat()

    # Changes the teacher made compared with what the camera recorded
    recognised = set(data.get("present", [])) & roster_usns
    overrides = [(u, "Present") for u in sorted(present - recognised)] + \
                [(u, "Absent") for u in sorted(recognised - present)]
    reasons = {}
    if overrides:
        asked = request.form.get("confirm_overrides") == "1"
        rows, missing = [], False
        for u, act in overrides:
            reason = request.form.get("reason_" + u, "").strip()
            note = request.form.get("note_" + u, "").strip()
            if reason not in OVERRIDE_REASONS[act] or (reason.startswith("Other") and not note):
                missing = True
            else:
                reasons[u] = (reason + (": " + note if note else ""))[:200]
            rows.append(dict(usn=u, name=names[u], action=act, options=OVERRIDE_REASONS[act],
                             reason=reason, note=note))
        if missing or not asked:
            return render_template("faculty/override_reason.html", token=token, class_date=class_date,
                                   present=sorted(present), rows=rows, data=data, error=asked and missing)

    old = db.query("""SELECT id FROM class_sessions WHERE faculty_id=? AND subject=? AND department=?
                      AND semester=? AND class_date=?""",
                   (data["faculty_id"], data["subject"], data["department"], data["semester"], class_date), one=True)
    if old:  # same class on the same day: replace the earlier record
        db.execute("DELETE FROM attendance WHERE session_id = ?", (old["id"],))
        db.execute("DELETE FROM class_sessions WHERE id = ?", (old["id"],))
    sid = db.execute("""INSERT INTO class_sessions (faculty_id, subject, department, semester, class_date)
                        VALUES (?,?,?,?,?)""",
                     (data["faculty_id"], data["subject"], data["department"], data["semester"], class_date))
    db.executemany("INSERT INTO attendance (session_id, usn, status) VALUES (?,?,?)",
                   [(sid, r["usn"], "P" if r["usn"] in present else "A") for r in roster])
    if overrides:
        db.executemany("""INSERT INTO attendance_overrides (session_id, faculty_id, usn, subject, class_date, action, reason)
                          VALUES (?,?,?,?,?,?,?)""",
                       [(sid, data["faculty_id"], u, data["subject"], class_date, act, reasons[u])
                        for u, act in overrides])
    os.remove(path)
    flash(f"Attendance saved: {len(present)} of {len(roster)} present"
          + (" (replaced the earlier record for that day)" if old else "")
          + (f". {len(overrides)} manual change(s) were recorded in the override log." if overrides else "."), "success")
    return redirect(url_for("faculty_dashboard", subject=data["subject"]))


@app.route("/faculty/overrides")
@login_required("faculty")
def faculty_overrides():
    rows = db.query("""SELECT o.*, st.name FROM attendance_overrides o LEFT JOIN students st ON st.usn = o.usn
                       WHERE o.faculty_id = ? ORDER BY o.id DESC LIMIT 300""", (session["faculty_id"],))
    return render_template("overrides.html", rows=rows, show_faculty=False,
                           heading="My override log",
                           lead="Every time you changed what the camera recorded, the reason is saved here.")


@app.route("/admin/overrides")
@login_required("admin")
def admin_overrides():
    rows = db.query("""SELECT o.*, st.name, f.full_name, f.username FROM attendance_overrides o
                       LEFT JOIN students st ON st.usn = o.usn LEFT JOIN faculty f ON f.id = o.faculty_id
                       ORDER BY o.id DESC LIMIT 500""")
    return render_template("overrides.html", rows=rows, show_faculty=True,
                           heading="Attendance override log",
                           lead="Manual changes made by faculty to the camera attendance, with the reason.")


@app.route("/faculty/monitor")
@login_required("faculty")
def faculty_monitor():
    fac = current_faculty()
    history = db.query("SELECT * FROM monitoring_sessions WHERE faculty_id = ? ORDER BY id DESC LIMIT 15",
                       (fac["id"],))
    return render_template("faculty/monitor.html", fac=fac, subjects=split_subjects(fac["subjects"]),
                           history=history)


@app.route("/faculty/monitor/start", methods=["POST"])
@login_required("faculty")
def faculty_monitor_start():
    fac = current_faculty()
    form = read_class_form(fac)
    if not form:
        flash("Choose a subject, department and semester.", "error")
        return redirect(url_for("faculty_monitor"))
    subject, department, semester = form
    roster = class_students(department, semester)
    if not roster:
        flash(f"No students are registered in {department}, semester {semester}.", "error")
        return redirect(url_for("faculty_monitor"))

    out = os.path.join(TMP_DIR, f"{uuid.uuid4().hex}_mon.json")
    run_script("monitor.py", "--out", out, "--allowed", ",".join(r["usn"] for r in roster))
    stats = {}
    if os.path.exists(out):
        with open(out) as f:
            stats = json.load(f)
        os.remove(out)
    stats = {u: c for u, c in stats.items() if c.get("samples", 0) > 0}
    if not stats:
        flash("No emotions were recorded. Make sure faces were visible and the camera ran for a while.", "error")
        return redirect(url_for("faculty_monitor"))

    scores = {u: engagement_score(c) for u, c in stats.items()}
    overall = round(sum(scores.values()) / len(scores), 1)
    mid = db.execute("""INSERT INTO monitoring_sessions (faculty_id, subject, department, semester,
                        overall_engagement, level) VALUES (?,?,?,?,?,?)""",
                     (fac["id"], subject, department, semester, overall, engagement_level(overall)))
    db.executemany("""INSERT INTO emotion_records (monitor_id, usn, happy, surprise, neutral, sad, fear,
                      angry, disgust, samples, engagement) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                   [(mid, u, *[c.get(e, 0) for e in EMOTIONS], c["samples"], scores[u])
                    for u, c in stats.items()])
    return redirect(url_for("faculty_monitor_result", mid=mid))


def own_monitor(mid):
    m = db.query("SELECT * FROM monitoring_sessions WHERE id = ? AND faculty_id = ?",
                 (mid, session["faculty_id"]), one=True)
    if not m:
        abort(404)
    return m


def monitor_data(m):
    recs = {r["usn"]: r for r in db.query("SELECT * FROM emotion_records WHERE monitor_id = ?", (m["id"],))}
    students, class_counts = [], {e: 0 for e in EMOTIONS}
    for s in class_students(m["department"], m["semester"]):
        r = recs.get(s["usn"])
        if r:
            counts = {e: r[e] for e in EMOTIONS}
            for e in EMOTIONS:
                class_counts[e] += counts[e]
            students.append(dict(usn=s["usn"], name=s["name"], counts=counts, samples=r["samples"],
                                 score=r["engagement"], level=engagement_level(r["engagement"]),
                                 dominant=max(counts, key=counts.get)))
        else:
            students.append(dict(usn=s["usn"], name=s["name"], counts=None, samples=0, score=None,
                                 level=None, dominant=None))
    seen = [s for s in students if s["counts"]]
    levels = {lv: len([s for s in seen if s["level"] == lv]) for lv in ("High", "Moderate", "Low")}
    return dict(students=students, seen=seen, class_counts=class_counts, levels=levels,
                missing=len(students) - len(seen))


@app.route("/faculty/monitor/<int:mid>")
@login_required("faculty")
def faculty_monitor_result(mid):
    m = own_monitor(mid)
    return render_template("faculty/monitor_result.html", m=m, **monitor_data(m))


@app.route("/faculty/monitor/<int:mid>.xlsx")
@login_required("faculty")
def faculty_monitor_export(mid):
    m = own_monitor(mid)
    return xlsx_response(reports.monitor_workbook(m, monitor_data(m)["students"], EMOTIONS),
                         f"engagement_{m['subject']}_{m['department']}{m['semester']}_{m['id']}.xlsx")


# ------------------------------------------------------------ marks (faculty)
def parse_mark(text, maximum):
    text = (text or "").strip()
    if text == "":
        return None
    value = float(text)
    if not 0 <= value <= maximum:
        raise ValueError
    return round(value, 1)


@app.route("/faculty/marks", methods=["GET", "POST"])
@login_required("faculty")
def faculty_marks():
    fac = current_faculty()
    subjects = split_subjects(fac["subjects"])
    src = request.form if request.method == "POST" else request.args
    subject, department, semester = src.get("subject", ""), src.get("department", ""), src.get("semester", type=int)
    roster, existing, has_lab = None, {}, False
    if subject in subjects and department and semester:
        roster = class_students(department, semester)
        has_lab = db.subject_has_lab(subject, department)
        existing = {r["usn"]: r for r in db.query("SELECT * FROM marks WHERE subject = ?", (subject,))}
        if request.method == "POST":
            rows, bad = [], []
            for st in roster:
                u = st["usn"]
                try:
                    internal1 = parse_mark(request.form.get(f"internal1_{u}"), INTERNAL1_MAX)
                    internal2 = parse_mark(request.form.get(f"internal2_{u}"), INTERNAL2_MAX)
                    assignment = parse_mark(request.form.get(f"assignment_{u}"), ASSIGNMENT_MAX)
                    activity = parse_mark(request.form.get(f"activity_{u}"), ACTIVITY_MAX)
                    lab = parse_mark(request.form.get(f"lab_{u}"), LAB_MAX) if has_lab else (
                        existing[u]["lab"] if u in existing else None)
                except ValueError:
                    bad.append(u)
                    continue
                rows.append((u, subject, internal1, internal2, assignment, activity, lab, fac["id"]))
            if bad:
                flash(f"Check the marks for {', '.join(bad)}: use numbers within the maximum.", "error")
            else:
                db.executemany("""INSERT INTO marks (usn, subject, internal1, internal2, assignment, activity, lab, faculty_id, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,datetime('now'))
                    ON CONFLICT(usn, subject) DO UPDATE SET internal1=excluded.internal1, internal2=excluded.internal2,
                    assignment=excluded.assignment, activity=excluded.activity,
                    lab=excluded.lab, faculty_id=excluded.faculty_id, updated_at=excluded.updated_at""", rows)
                flash(f"Marks saved for {len(rows)} students in {subject}.", "success")
                return redirect(url_for("faculty_marks", subject=subject, department=department, semester=semester))
            existing = {u: dict(internal1=request.form.get(f"internal1_{u}"), internal2=request.form.get(f"internal2_{u}"),
                                assignment=request.form.get(f"assignment_{u}"), activity=request.form.get(f"activity_{u}"),
                                lab=request.form.get(f"lab_{u}")) for u in (r["usn"] for r in roster)}
    return render_template("faculty/marks.html", fac=fac, subjects=subjects, subject=subject, department=department,
                           semester=semester, roster=roster, existing=existing, has_lab=has_lab)


# ----------------------------------------------------------- events (faculty)
@app.route("/faculty/events", methods=["GET", "POST"])
@login_required("faculty")
def faculty_events():
    fac = current_faculty()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Give the event a title.", "error")
            return redirect(url_for("faculty_events"))
        filename = None
        img = request.files.get("image")
        if img and img.filename:
            ext = secure_filename(img.filename).rsplit(".", 1)[-1].lower()
            if ext not in IMAGE_EXT:
                flash("Use a PNG, JPG, GIF or WEBP image.", "error")
                return redirect(url_for("faculty_events"))
            filename = f"{uuid.uuid4().hex}.{ext}"
            img.save(os.path.join(EVENT_DIR, filename))
        db.execute("""INSERT INTO events (faculty_id, title, description, venue, event_date, image)
                      VALUES (?,?,?,?,?,?)""",
                   (fac["id"], title, request.form.get("description", "").strip(),
                    request.form.get("venue", "").strip(), request.form.get("event_date", ""), filename))
        flash("Event published. Students can see it now.", "success")
        return redirect(url_for("faculty_events"))
    events = db.query("SELECT * FROM events WHERE faculty_id = ? ORDER BY id DESC", (fac["id"],))
    return render_template("faculty/events.html", events=events)


@app.route("/faculty/events/<int:eid>/delete", methods=["POST"])
@login_required("faculty")
def faculty_delete_event(eid):
    ev = db.query("SELECT * FROM events WHERE id = ? AND faculty_id = ?", (eid, session["faculty_id"]), one=True)
    if ev:
        if ev["image"]:
            try:
                os.remove(os.path.join(EVENT_DIR, ev["image"]))
            except OSError:
                pass
        db.execute("DELETE FROM events WHERE id = ?", (eid,))
        flash("Event removed.", "info")
    return redirect(url_for("faculty_events"))


# ------------------------------------------------- study material (notes, assignments, quiz links)
def remove_material_file(filename):
    if filename:
        try:
            os.remove(os.path.join(MATERIAL_DIR, filename))
        except OSError:
            pass


def clean_link(text):
    """Only plain http(s) links are accepted (blocks javascript: and similar)."""
    text = (text or "").strip()
    if len(text) > 600 or not re.match(r"^https?://[^\s]+$", text, re.I):
        return None
    return text


def clean_date(text):
    try:
        return date.fromisoformat((text or "").strip()).isoformat()
    except ValueError:
        return None


# who may see a material: one class, a whole department, everyone, or named students
VISIBLE_TO_STUDENT = """(COALESCE(m.audience, 'class') = 'all'
    OR (m.audience = 'department' AND m.department = :dept)
    OR (COALESCE(m.audience, 'class') = 'class' AND m.department = :dept AND m.semester = :sem)
    OR (m.audience = 'students' AND EXISTS (SELECT 1 FROM material_students ms
                                            WHERE ms.material_id = m.id AND ms.usn = :usn)))"""


@app.route("/faculty/materials", methods=["GET", "POST"])
@login_required("faculty")
def faculty_materials():
    fac = current_faculty()
    subjects = split_subjects(fac["subjects"])
    if request.method == "POST":
        kind = request.form.get("kind", "")
        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "")
        department = request.form.get("department", "")
        semester = request.form.get("semester", type=int)
        if kind not in MATERIAL_KINDS or not title:
            flash("Choose what you are sharing and give it a title.", "error")
            return redirect(url_for("faculty_materials"))
        audience = request.form.get("audience", "class")
        usns = []
        if subject not in subjects:
            flash("Choose one of your subjects.", "error")
            return redirect(url_for("faculty_materials"))
        if audience == "class":
            if (not semester or not 1 <= semester <= 8
                    or not db.query("SELECT 1 FROM departments WHERE code = ?", (department,), one=True)):
                flash("Choose the department and semester for the students.", "error")
                return redirect(url_for("faculty_materials"))
        elif audience == "department":
            if not db.query("SELECT 1 FROM departments WHERE code = ?", (department,), one=True):
                flash("Choose the department.", "error")
                return redirect(url_for("faculty_materials"))
            semester = 0
        elif audience == "all":
            department, semester = "ALL", 0
        elif audience == "students":
            for u in request.form.getlist("student_usns"):
                if u not in usns and db.query("SELECT 1 FROM students WHERE usn = ?", (u,), one=True):
                    usns.append(u)
            if not usns:
                flash("Tick at least one student.", "error")
                return redirect(url_for("faculty_materials"))
            department, semester = "ALL", 0
        else:
            flash("Choose who should receive it.", "error")
            return redirect(url_for("faculty_materials"))
        filename = original = link = None
        if kind == "quiz":
            link = clean_link(request.form.get("link"))
            if not link:
                flash("Paste the full quiz link, starting with https://", "error")
                return redirect(url_for("faculty_materials"))
        else:
            up = request.files.get("file")
            if not up or not up.filename:
                flash("Choose a PDF file to upload.", "error")
                return redirect(url_for("faculty_materials"))
            if not up.filename.lower().endswith(".pdf") or up.stream.read(5) != b"%PDF-":
                flash("Only PDF files can be uploaded.", "error")
                return redirect(url_for("faculty_materials"))
            up.stream.seek(0)
            original = secure_filename(up.filename) or "document.pdf"
            if not original.lower().endswith(".pdf"):
                original += ".pdf"
            filename = f"{uuid.uuid4().hex}.pdf"
            up.save(os.path.join(MATERIAL_DIR, filename))
        mid = db.execute("""INSERT INTO materials (faculty_id, kind, title, subject, department, semester,
                      description, filename, original_name, link, due_date, audience) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (fac["id"], kind, title, subject, department, semester,
                    request.form.get("description", "").strip(), filename, original, link,
                    clean_date(request.form.get("due_date")), audience))
        for u in usns:
            db.execute("INSERT OR IGNORE INTO material_students (material_id, usn) VALUES (?,?)", (mid, u))
        who = {"class": f"semester {semester} {department} students",
               "department": f"all semesters of {department}",
               "all": "every student",
               "students": f"{len(usns)} selected student{'s' if len(usns) != 1 else ''}"}[audience]
        flash(f"{MATERIAL_KINDS[kind]} shared with {who}.", "success")
        return redirect(url_for("faculty_materials"))
    items = db.query("SELECT m.*, (SELECT COUNT(*) FROM material_students ms WHERE ms.material_id = m.id) AS n_students "
                     "FROM materials m WHERE m.faculty_id = ? ORDER BY m.id DESC", (fac["id"],))
    students = db.query("SELECT usn, name, department, semester FROM students ORDER BY department, semester, usn")
    return render_template("faculty/materials.html", fac=fac, subjects=subjects, items=items,
                           kinds=MATERIAL_KINDS, students=students)


@app.route("/faculty/materials/<int:mid>/delete", methods=["POST"])
@login_required("faculty")
def faculty_delete_material(mid):
    m = db.query("SELECT * FROM materials WHERE id = ? AND faculty_id = ?", (mid, session["faculty_id"]), one=True)
    if m:
        remove_material_file(m["filename"])
        db.execute("DELETE FROM material_students WHERE material_id = ?", (mid,))
        db.execute("DELETE FROM materials WHERE id = ?", (mid,))
        flash("Removed. Students can no longer see it.", "info")
    return redirect(url_for("faculty_materials"))


@app.route("/materials/<int:mid>/download")
def material_download(mid):
    m = db.query("SELECT * FROM materials WHERE id = ?", (mid,), one=True)
    if not m or not m["filename"]:
        abort(404)
    role = session.get("role")
    if role == "faculty":
        if session.get("faculty_id") != m["faculty_id"]:
            abort(403)
    elif role == "student":
        st = db.query("SELECT usn, department, semester FROM students WHERE usn = ?", (session.get("usn"),), one=True)
        if not st or not db.query(f"SELECT 1 FROM materials m WHERE m.id = :mid AND {VISIBLE_TO_STUDENT}",
                                  {"mid": mid, "dept": st["department"], "sem": st["semester"], "usn": st["usn"]},
                                  one=True):
            abort(403)
    else:
        flash("Please sign in to continue.", "info")
        return redirect(url_for("login"))
    return send_from_directory(MATERIAL_DIR, m["filename"], as_attachment=True,
                               download_name=m["original_name"] or "document.pdf")


@app.route("/student/materials")
@login_required("student")
def student_materials():
    st = db.query("SELECT * FROM students WHERE usn = ?", (session["usn"],), one=True)
    if not st:
        session.clear()
        return redirect(url_for("login"))
    kind = request.args.get("kind", "")
    sql = ("SELECT m.*, f.full_name, f.username FROM materials m JOIN faculty f ON f.id = m.faculty_id "
           f"WHERE {VISIBLE_TO_STUDENT}")
    args = {"dept": st["department"], "sem": st["semester"], "usn": st["usn"]}
    if kind in MATERIAL_KINDS:
        sql += " AND m.kind = :kind"
        args["kind"] = kind
    items = db.query(sql + " ORDER BY m.subject, m.id DESC", args)
    subjects = {}
    for m in items:
        subjects.setdefault(m["subject"], []).append(m)
    return render_template("student/materials.html", st=st, subjects=subjects, kind=kind,
                           kinds=MATERIAL_KINDS, total=len(items))


@app.errorhandler(413)
def too_large(_):
    flash("That file is too large. Uploads can be up to 25 MB.", "error")
    return redirect(request.referrer or url_for("home"))


# ------------------------------------------------------------ leaves (faculty)
def leaves_for_faculty(fid):
    """Leave requests addressed to this faculty (older requests with no faculty chosen keep the old rule)."""
    return db.query("""
        SELECT l.*, s.name, s.department, s.semester FROM leaves l JOIN students s ON s.usn = l.usn
        WHERE l.faculty_id = ?
           OR (l.faculty_id IS NULL AND (
                s.department = (SELECT department FROM faculty WHERE id = ?)
                OR EXISTS (SELECT 1 FROM class_sessions cs WHERE cs.faculty_id = ?
                           AND cs.department = s.department AND cs.semester = s.semester)))
        ORDER BY CASE l.status WHEN 'Pending' THEN 0 ELSE 1 END, l.id DESC""", (fid, fid, fid))


@app.route("/faculty/leaves")
@login_required("faculty")
def faculty_leaves():
    rows = leaves_for_faculty(session["faculty_id"])
    return render_template("faculty/leaves.html", pending=[r for r in rows if r["status"] == "Pending"],
                           decided=[r for r in rows if r["status"] != "Pending"])


@app.route("/faculty/leaves/<int:lid>/decide", methods=["POST"])
@login_required("faculty")
def faculty_decide_leave(lid):
    row = next((r for r in leaves_for_faculty(session["faculty_id"]) if r["id"] == lid), None)
    decision = {"approve": "Approved", "reject": "Rejected"}.get(request.form.get("decision"))
    if not row or not decision or row["status"] != "Pending":
        abort(400)
    db.execute("""UPDATE leaves SET status = ?, faculty_comment = ?, decided_by = ?, decided_at = datetime('now')
                  WHERE id = ?""", (decision, request.form.get("comment", "").strip(), session["faculty_id"], lid))
    flash(f"Leave for {row['name']} {decision.lower()}.", "success")
    return redirect(url_for("faculty_leaves"))


# ----------------------------------------------------------------- reports
def xlsx_response(wb, filename):
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name=filename.replace(" ", "_"), mimetype=XLSX)


@app.route("/admin/reports")
@login_required("admin")
def admin_reports():
    return render_template("admin/reports.html",
                           students=db.query("SELECT usn, name, department, semester FROM students ORDER BY usn"))


@app.route("/admin/reports/class.xlsx")
@login_required("admin")
def admin_report_class():
    d, sem = request.args.get("department", ""), request.args.get("semester", type=int)
    return xlsx_response(reports.class_workbook(d or None, sem), f"class_report_{d or 'all'}_{sem or 'all'}.xlsx")


@app.route("/admin/reports/student/<usn>.xlsx")
@login_required("admin")
def admin_report_student(usn):
    if not db.query("SELECT 1 FROM students WHERE usn = ?", (usn,), one=True):
        abort(404)
    return xlsx_response(reports.student_workbook(usn), f"student_report_{usn}.xlsx")


@app.route("/faculty/reports")
@login_required("faculty")
def faculty_reports():
    fac = current_faculty()
    students = db.query("""SELECT DISTINCT st.usn, st.name, st.department, st.semester FROM students st
                           JOIN attendance a ON a.usn = st.usn JOIN class_sessions cs ON cs.id = a.session_id
                           WHERE cs.faculty_id = ? ORDER BY st.usn""", (fac["id"],))
    return render_template("faculty/reports.html", fac=fac, subjects=split_subjects(fac["subjects"]), students=students)


@app.route("/faculty/reports/subject.xlsx")
@login_required("faculty")
def faculty_report_subject():
    fac = current_faculty()
    subject, d, sem = request.args.get("subject", ""), request.args.get("department", ""), request.args.get("semester", type=int)
    if subject not in split_subjects(fac["subjects"]) or not d or not sem:
        abort(400)
    return xlsx_response(reports.class_workbook(d, sem, subject=subject, faculty_id=fac["id"]),
                         f"{subject}_{d}{sem}_report.xlsx")


@app.route("/faculty/reports/student/<usn>.xlsx")
@login_required("faculty")
def faculty_report_student(usn):
    fac = current_faculty()
    if not db.query("SELECT 1 FROM students WHERE usn = ?", (usn,), one=True):
        abort(404)
    return xlsx_response(reports.student_workbook(usn, subjects=split_subjects(fac["subjects"]), include_leaves=False),
                         f"student_report_{usn}.xlsx")


# ---------------------------------------------------------------- student
@app.route("/student")
@login_required("student")
def student_dashboard():
    usn = session["usn"]
    st = db.query("SELECT * FROM students WHERE usn = ?", (usn,), one=True)
    if not st:
        session.clear()
        return redirect(url_for("login"))
    subj = db.subject_attendance(usn)
    total, present = sum(s["total"] for s in subj), sum(s["present"] for s in subj)
    latest_leave = db.query("SELECT * FROM leaves WHERE usn = ? ORDER BY id DESC LIMIT 1", (usn,), one=True)
    events = db.query("SELECT e.*, f.full_name, f.username FROM events e JOIN faculty f ON f.id = e.faculty_id "
                      "ORDER BY e.id DESC LIMIT 3")
    return render_template("student/dashboard.html", st=st, subj=subj, total=total, present=present,
                           overall=pct(present, total), marks=db.student_marks(usn),
                           latest_leave=latest_leave, events=events)


@app.route("/student/report.xlsx")
@login_required("student")
def student_report():
    return xlsx_response(reports.student_workbook(session["usn"]), f"my_report_{session['usn']}.xlsx")


@app.route("/student/events")
@login_required("student")
def student_events():
    events = db.query("SELECT e.*, f.full_name, f.username, f.department FROM events e "
                      "JOIN faculty f ON f.id = e.faculty_id ORDER BY e.id DESC")
    return render_template("student/events.html", events=events)


@app.route("/student/leave", methods=["GET", "POST"])
@login_required("student")
def student_leave():
    usn = session["usn"]
    if request.method == "POST":
        f, t = request.form.get("from_date", ""), request.form.get("to_date", "")
        reason = request.form.get("reason", "").strip()
        fids = []
        for x in request.form.getlist("faculty_ids"):
            if x.isdigit() and int(x) not in fids:
                fids.append(int(x))
        chosen = [r for r in (db.query("SELECT id, full_name, username FROM faculty WHERE id = ?", (i,), one=True)
                              for i in fids) if r]
        if not (f and t and reason):
            flash("Add the dates and a reason for the leave.", "error")
        elif not chosen:
            flash("Choose at least one faculty member to receive this request.", "error")
        elif t < f:
            flash("The end date cannot be before the start date.", "error")
        else:
            # one request per chosen faculty, so each of them can approve or reject on their own
            for fr in chosen:
                db.execute("INSERT INTO leaves (usn, from_date, to_date, reason, faculty_id) VALUES (?,?,?,?,?)",
                           (usn, f, t, reason, fr["id"]))
            names = ", ".join(fr["full_name"] or fr["username"] for fr in chosen)
            flash(f"Leave request sent to {names}.", "success")
        return redirect(url_for("student_leave"))
    leaves = db.query("""SELECT l.*, f.full_name, f.username, t.full_name AS to_name, t.username AS to_username
                         FROM leaves l LEFT JOIN faculty f ON f.id = l.decided_by
                         LEFT JOIN faculty t ON t.id = l.faculty_id
                         WHERE l.usn = ? ORDER BY l.id DESC""", (usn,))
    st = db.query("SELECT department FROM students WHERE usn = ?", (usn,), one=True)
    faculty_list = db.query("SELECT id, full_name, username, department, subjects FROM faculty "
                            "ORDER BY CASE WHEN department = ? THEN 0 ELSE 1 END, full_name",
                            (st["department"] if st else "",))
    return render_template("student/leave.html", leaves=leaves, faculty_list=faculty_list,
                           today=date.today().isoformat())


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)

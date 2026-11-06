"""SQLite layer for the attendance + engagement system (uses the sqlite3 module)."""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "attendance.db")

DEFAULT_DEPARTMENTS = [
    ("CSE", "Computer Science & Engineering"),
    ("ISE", "Information Science & Engineering"),
    ("AIML", "Artificial Intelligence & Machine Learning"),
    ("ECE", "Electronics & Communication"),
    ("EEE", "Electrical & Electronics"),
    ("ME", "Mechanical Engineering"),
    ("CV", "Civil Engineering"),
]

INTERNAL1_MAX, INTERNAL2_MAX, ASSIGNMENT_MAX, ACTIVITY_MAX, LAB_MAX = 25, 25, 10, 5, 30

# (subject, department or ALL, semester, has_lab)
SUBJECT_CATALOG = [
    ("Engineering Mathematics", "ALL", 1, 0), ("Engineering Physics", "ALL", 1, 1),
    ("Engineering Chemistry", "ALL", 2, 1), ("Communication Skills", "ALL", 2, 0),
    ("Environmental Studies", "ALL", 4, 0), ("Professional Ethics", "ALL", 8, 0),
    # Computer Science
    ("Data Structures", "CSE", 3, 1), ("Database Management Systems", "CSE", 4, 1),
    ("Operating Systems", "CSE", 4, 1), ("Design and Analysis of Algorithms", "CSE", 4, 1),
    ("Computer Networks", "CSE", 5, 1), ("Software Engineering", "CSE", 5, 0),
    ("Web Technologies", "CSE", 5, 1), ("Compiler Design", "CSE", 6, 1),
    ("Machine Learning", "CSE", 6, 1), ("Cloud Computing", "CSE", 7, 0),
    # Information Science
    ("Python Programming", "ISE", 3, 1), ("Data Structures and Applications", "ISE", 3, 1),
    ("Database Management Systems", "ISE", 4, 1), ("Computer Networks", "ISE", 5, 1),
    ("Cryptography and Network Security", "ISE", 6, 0), ("Software Testing", "ISE", 6, 1),
    ("Data Mining", "ISE", 6, 0), ("Big Data Analytics", "ISE", 7, 1), ("Internet of Things", "ISE", 7, 0),
    # AI & ML
    ("Python for Data Science", "AIML", 3, 1), ("Mathematics for Machine Learning", "AIML", 3, 0),
    ("Artificial Intelligence", "AIML", 4, 0), ("Machine Learning", "AIML", 5, 1),
    ("Deep Learning", "AIML", 6, 1), ("Natural Language Processing", "AIML", 6, 1),
    ("Computer Vision", "AIML", 7, 1), ("Reinforcement Learning", "AIML", 7, 0),
    # Electronics & Communication
    ("Analog Electronics", "ECE", 3, 1), ("Digital Electronics", "ECE", 3, 1),
    ("Signals and Systems", "ECE", 4, 0), ("Microprocessors", "ECE", 4, 1),
    ("Communication Systems", "ECE", 5, 1), ("Digital Signal Processing", "ECE", 5, 1),
    ("VLSI Design", "ECE", 6, 1), ("Embedded Systems", "ECE", 6, 1), ("Antenna Theory", "ECE", 7, 0),
    # Electrical & Electronics
    ("Electric Circuits", "EEE", 3, 1), ("Electrical Machines", "EEE", 4, 1),
    ("Electrical Measurements", "EEE", 4, 1), ("Power Electronics", "EEE", 5, 1),
    ("Control Systems", "EEE", 5, 0), ("Power Systems", "EEE", 6, 1),
    ("Switchgear and Protection", "EEE", 7, 0), ("High Voltage Engineering", "EEE", 7, 0),
    # Mechanical
    ("Engineering Thermodynamics", "ME", 3, 0), ("Fluid Mechanics", "ME", 3, 1),
    ("Strength of Materials", "ME", 4, 1), ("Manufacturing Processes", "ME", 4, 1),
    ("Theory of Machines", "ME", 5, 0), ("Heat Transfer", "ME", 5, 1),
    ("Machine Design", "ME", 6, 0), ("CAD/CAM", "ME", 7, 1), ("Robotics", "ME", 7, 0),
    # Civil
    ("Surveying", "CV", 3, 1), ("Strength of Materials", "CV", 3, 1),
    ("Fluid Mechanics and Hydraulics", "CV", 4, 1), ("Structural Analysis", "CV", 4, 0),
    ("Concrete Technology", "CV", 5, 1), ("Geotechnical Engineering", "CV", 5, 1),
    ("Transportation Engineering", "CV", 6, 1), ("Environmental Engineering", "CV", 6, 1),
    ("Design of RCC Structures", "CV", 7, 0), ("Construction Management", "CV", 8, 0),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS students (
    usn TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    semester INTEGER NOT NULL,
    department TEXT NOT NULL,
    registered_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS faculty (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    full_name TEXT,
    password_hash TEXT NOT NULL,
    department TEXT NOT NULL,
    subjects TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS class_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    department TEXT NOT NULL,
    semester INTEGER NOT NULL,
    class_date TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    usn TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('P','A')),
    UNIQUE (session_id, usn)
);
CREATE TABLE IF NOT EXISTS monitoring_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    department TEXT NOT NULL,
    semester INTEGER NOT NULL,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    overall_engagement REAL,
    level TEXT
);
CREATE TABLE IF NOT EXISTS emotion_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monitor_id INTEGER NOT NULL,
    usn TEXT NOT NULL,
    happy INTEGER DEFAULT 0,
    surprise INTEGER DEFAULT 0,
    neutral INTEGER DEFAULT 0,
    sad INTEGER DEFAULT 0,
    fear INTEGER DEFAULT 0,
    angry INTEGER DEFAULT 0,
    disgust INTEGER DEFAULT 0,
    samples INTEGER DEFAULT 0,
    engagement REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    department TEXT NOT NULL,          -- department code, or ALL for common subjects
    semester INTEGER,
    has_lab INTEGER DEFAULT 0,
    UNIQUE (name, department)
);
CREATE TABLE IF NOT EXISTS marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usn TEXT NOT NULL,
    subject TEXT NOT NULL,
    internal REAL,
    activity REAL,
    lab REAL,
    internal1 REAL,
    internal2 REAL,
    assignment REAL,
    faculty_id INTEGER,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (usn, subject)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    venue TEXT,
    event_date TEXT,
    image TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    subject TEXT NOT NULL,
    department TEXT NOT NULL,
    semester INTEGER NOT NULL,
    description TEXT,
    filename TEXT,
    original_name TEXT,
    link TEXT,
    due_date TEXT,
    audience TEXT DEFAULT 'class',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS material_students (
    material_id INTEGER NOT NULL,
    usn TEXT NOT NULL,
    PRIMARY KEY (material_id, usn)
);
CREATE TABLE IF NOT EXISTS leaves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usn TEXT NOT NULL,
    from_date TEXT NOT NULL,
    to_date TEXT NOT NULL,
    reason TEXT NOT NULL,
    faculty_id INTEGER,
    status TEXT NOT NULL DEFAULT 'Pending',
    faculty_comment TEXT,
    decided_by INTEGER,
    decided_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    # upgrade older databases that were created before the new marks / leave columns
    def _add(table, col, decl):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    _add("marks", "internal1", "REAL")
    _add("marks", "internal2", "REAL")
    _add("marks", "assignment", "REAL")
    _add("leaves", "faculty_id", "INTEGER")
    _add("materials", "audience", "TEXT DEFAULT 'class'")
    conn.executemany(
        "INSERT OR IGNORE INTO departments (code, name) VALUES (?, ?)", DEFAULT_DEPARTMENTS
    )
    conn.executemany(
        "INSERT OR IGNORE INTO subjects (name, department, semester, has_lab) VALUES (?,?,?,?)",
        SUBJECT_CATALOG,
    )
    conn.commit()
    conn.close()


def query(sql, args=(), one=False):
    conn = get_conn()
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    """Run a write statement; returns lastrowid."""
    conn = get_conn()
    cur = conn.execute(sql, args)
    conn.commit()
    last = cur.lastrowid
    conn.close()
    return last


def executemany(sql, seq):
    conn = get_conn()
    conn.executemany(sql, seq)
    conn.commit()
    conn.close()


# ---------- convenience queries ----------
def get_stats():
    return {
        "students": query("SELECT COUNT(*) c FROM students", one=True)["c"],
        "departments": query("SELECT COUNT(*) c FROM departments", one=True)["c"],
        "faculty": query("SELECT COUNT(*) c FROM faculty", one=True)["c"],
    }


def student_attendance(department=None, semester=None, search=None):
    sql = """
        SELECT s.usn, s.name, s.semester, s.department,
               COUNT(a.id) AS total,
               COALESCE(SUM(a.status = 'P'), 0) AS present
        FROM students s LEFT JOIN attendance a ON a.usn = s.usn
        WHERE 1=1
    """
    args = []
    if department:
        sql += " AND s.department = ?"
        args.append(department)
    if semester:
        sql += " AND s.semester = ?"
        args.append(semester)
    if search:
        sql += " AND (s.usn LIKE ? OR s.name LIKE ?)"
        args += [f"%{search}%", f"%{search}%"]
    sql += " GROUP BY s.usn ORDER BY s.department, s.semester, s.usn"
    rows = []
    for r in query(sql, args):
        d = dict(r)
        d["percent"] = round(d["present"] * 100 / d["total"], 1) if d["total"] else None
        rows.append(d)
    return rows


def subject_attendance(usn, subjects=None):
    """Attendance per subject for one student (optionally limited to some subjects)."""
    rows = query("""SELECT cs.subject, COUNT(a.id) total, SUM(a.status='P') present
                    FROM attendance a JOIN class_sessions cs ON cs.id = a.session_id
                    WHERE a.usn = ? GROUP BY cs.subject ORDER BY cs.subject""", (usn,))
    out = []
    for r in rows:
        if subjects is not None and r["subject"] not in subjects:
            continue
        d = dict(r)
        d["present"] = d["present"] or 0
        d["percent"] = round(d["present"] * 100 / d["total"], 1) if d["total"] else None
        out.append(d)
    return out


def student_marks(usn, subjects=None):
    rows = query("SELECT * FROM marks WHERE usn = ? ORDER BY subject", (usn,))
    out = []
    for r in rows:
        if subjects is not None and r["subject"] not in subjects:
            continue
        d = dict(r)
        parts = [(d["internal1"], INTERNAL1_MAX), (d["internal2"], INTERNAL2_MAX),
                 (d["assignment"], ASSIGNMENT_MAX), (d["activity"], ACTIVITY_MAX), (d["lab"], LAB_MAX)]
        given = [(v, m) for v, m in parts if v is not None]
        d["total"] = round(sum(v for v, _ in given), 1) if given else None
        d["out_of"] = sum(m for _, m in given)
        out.append(d)
    return out


def subject_has_lab(subject, department):
    r = query("SELECT 1 FROM subjects WHERE name = ? AND has_lab = 1 AND department IN (?, 'ALL')",
              (subject, department), one=True)
    return bool(r)

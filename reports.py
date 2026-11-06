"""Excel report builders (openpyxl). Each function returns an openpyxl Workbook."""
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import database as db

HEAD_FILL = PatternFill("solid", fgColor="10303A")
HEAD_FONT = Font(bold=True, color="FFFFFF")
LOW_FILL = PatternFill("solid", fgColor="FBDCD8")
OK_FILL = PatternFill("solid", fgColor="DDF2EA")
THRESHOLD = 75


def _table(ws, headers, rows, pct_cols=(), flag_cols=()):
    """Write a styled table starting at A1. pct_cols get a % format, flag_cols are
    colour-coded against the attendance threshold."""
    ws.append(headers)
    for c in ws[1]:
        c.fill, c.font = HEAD_FILL, HEAD_FONT
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for r in rows:
        ws.append(list(r))
    for row in ws.iter_rows(min_row=2):
        for i in pct_cols:
            row[i].number_format = '0.0"%"'
        for i in flag_cols:
            v = row[i].value
            if isinstance(v, (int, float)):
                row[i].fill = LOW_FILL if v < THRESHOLD else OK_FILL
    for i, h in enumerate(headers, start=1):
        width = max([len(str(h))] + [len(str(r[i - 1])) for r in rows if r[i - 1] is not None] + [8])
        ws.column_dimensions[get_column_letter(i)].width = min(width + 3, 42)
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 30


def _pct(present, total):
    return round(present * 100 / total, 1) if total else None


def _about(wb, title, lines):
    ws = wb.create_sheet("About")
    ws["A1"], ws["A1"].font = title, Font(bold=True, size=14)
    ws.append([])
    for k, v in lines:
        ws.append([k, v])
    ws.append(["Generated", datetime.now().strftime("%Y-%m-%d %H:%M")])
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 50


# ------------------------------------------------------------------ student
def student_workbook(usn, subjects=None, include_leaves=True):
    """One student: profile, attendance by subject, class log, marks, leaves.
    `subjects` limits the data to those subjects (used for faculty)."""
    st = db.query("SELECT * FROM students WHERE usn = ?", (usn,), one=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"

    subj = db.subject_attendance(usn, subjects)
    total = sum(s["total"] for s in subj)
    present = sum(s["present"] for s in subj)
    rows = [(s["subject"], s["total"], s["present"], s["total"] - s["present"], s["percent"]) for s in subj]
    rows.append(("Overall", total, present, total - present, _pct(present, total)))
    _table(ws, ["Subject", "Classes", "Present", "Absent", "Attendance"], rows, pct_cols=[4], flag_cols=[4])
    ws.cell(ws.max_row, 1).font = Font(bold=True)

    log = db.query("""SELECT cs.class_date, cs.subject, a.status FROM attendance a
                      JOIN class_sessions cs ON cs.id = a.session_id WHERE a.usn = ?
                      ORDER BY cs.class_date, cs.id""", (usn,))
    ws = wb.create_sheet("Class log")
    _table(ws, ["Date", "Subject", "Status"],
           [(r["class_date"], r["subject"], "Present" if r["status"] == "P" else "Absent")
            for r in log if subjects is None or r["subject"] in subjects])

    ws = wb.create_sheet("Marks")
    m = db.student_marks(usn, subjects)
    _table(ws, ["Subject", f"Internal 1 (/{db.INTERNAL1_MAX})", f"Internal 2 (/{db.INTERNAL2_MAX})",
                f"Assignment (/{db.ASSIGNMENT_MAX})", f"Activity (/{db.ACTIVITY_MAX})",
                f"Lab (/{db.LAB_MAX})", "Total", "Out of"],
           [(x["subject"], x["internal1"], x["internal2"], x["assignment"], x["activity"], x["lab"],
             x["total"], x["out_of"]) for x in m])

    if include_leaves:
        ws = wb.create_sheet("Leaves")
        lv = db.query("SELECT * FROM leaves WHERE usn = ? ORDER BY id DESC", (usn,))
        _table(ws, ["From", "To", "Reason", "Status", "Faculty comment"],
               [(l["from_date"], l["to_date"], l["reason"], l["status"], l["faculty_comment"]) for l in lv])

    _about(wb, "Student report", [("USN", usn), ("Name", st["name"]), ("Department", st["department"]),
                                  ("Semester", st["semester"])])
    wb.move_sheet("About", offset=-(len(wb.sheetnames) - 1))
    return wb


# -------------------------------------------------------------------- class
def class_workbook(department=None, semester=None, subject=None, faculty_id=None, subjects=None):
    """Whole class / department. With `subject` it also adds a day-by-day register."""
    sql, args = "SELECT usn, name, department, semester FROM students WHERE 1=1", []
    if department:
        sql += " AND department = ?"; args.append(department)
    if semester:
        sql += " AND semester = ?"; args.append(int(semester))
    students = db.query(sql + " ORDER BY department, semester, usn", args)
    usns = {s["usn"] for s in students}

    asql = """SELECT a.usn, cs.subject, cs.class_date, a.status FROM attendance a
              JOIN class_sessions cs ON cs.id = a.session_id WHERE 1=1"""
    aargs = []
    if subject:
        asql += " AND cs.subject = ?"; aargs.append(subject)
    if faculty_id:
        asql += " AND cs.faculty_id = ?"; aargs.append(faculty_id)
    att = [r for r in db.query(asql + " ORDER BY cs.class_date", aargs) if r["usn"] in usns]
    if subjects is not None:
        att = [r for r in att if r["subject"] in subjects]

    subj_list = sorted({r["subject"] for r in att})
    per = {}
    for r in att:
        d = per.setdefault((r["usn"], r["subject"]), [0, 0])
        d[1] += 1
        d[0] += r["status"] == "P"

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"
    headers = ["USN", "Name", "Dept", "Sem"] + [f"{s} %" for s in subj_list] + ["Classes", "Present", "Overall %"]
    rows = []
    for st in students:
        cells, tp, tt = [], 0, 0
        for sj in subj_list:
            p, t = per.get((st["usn"], sj), [0, 0])
            cells.append(_pct(p, t)); tp += p; tt += t
        rows.append([st["usn"], st["name"], st["department"], st["semester"], *cells, tt, tp, _pct(tp, tt)])
    n = len(subj_list)
    cols = list(range(4, 4 + n)) + [6 + n]
    _table(ws, headers, rows, pct_cols=cols, flag_cols=cols)

    if subject:
        dates = sorted({r["class_date"] for r in att})
        status = {(r["usn"], r["class_date"]): r["status"] for r in att}
        ws = wb.create_sheet("Daily register")
        _table(ws, ["USN", "Name"] + dates,
               [[s["usn"], s["name"]] + [status.get((s["usn"], d), "") for d in dates] for s in students])
        for row in ws.iter_rows(min_row=2, min_col=3):
            for c in row:
                c.alignment = Alignment(horizontal="center")
                if c.value == "A":
                    c.fill = LOW_FILL
                elif c.value == "P":
                    c.fill = OK_FILL

    name = {s["usn"]: s["name"] for s in students}
    mrows = []
    for r in db.query("SELECT * FROM marks ORDER BY subject, usn"):
        if r["usn"] not in usns or (subject and r["subject"] != subject):
            continue
        if subjects is not None and r["subject"] not in subjects:
            continue
        parts = [(r["internal1"], db.INTERNAL1_MAX), (r["internal2"], db.INTERNAL2_MAX),
                 (r["assignment"], db.ASSIGNMENT_MAX), (r["activity"], db.ACTIVITY_MAX), (r["lab"], db.LAB_MAX)]
        given = [(v, m) for v, m in parts if v is not None]
        mrows.append([r["usn"], name[r["usn"]], r["subject"], r["internal1"], r["internal2"], r["assignment"], r["activity"], r["lab"],
                      round(sum(v for v, _ in given), 1) if given else None, sum(m for _, m in given)])
    ws = wb.create_sheet("Marks")
    _table(ws, ["USN", "Name", "Subject", f"Internal 1 (/{db.INTERNAL1_MAX})", f"Internal 2 (/{db.INTERNAL2_MAX})",
                f"Assignment (/{db.ASSIGNMENT_MAX})", f"Activity (/{db.ACTIVITY_MAX})",
                f"Lab (/{db.LAB_MAX})", "Total", "Out of"], mrows)

    _about(wb, "Class report", [("Department", department or "All"), ("Semester", semester or "All"),
                                ("Subject", subject or "All"), ("Students", len(students))])
    wb.move_sheet("About", offset=-(len(wb.sheetnames) - 1))
    return wb


# --------------------------------------------------------------- engagement
def monitor_workbook(m, students, emotions):
    wb = Workbook()
    ws = wb.active
    ws.title = "Engagement"
    rows = []
    for s in students:
        if s["counts"]:
            rows.append([s["usn"], s["name"], *[s["counts"][e] for e in emotions], s["samples"], s["score"], s["level"]])
        else:
            rows.append([s["usn"], s["name"], *[None] * len(emotions), 0, None, "Not seen"])
    _table(ws, ["USN", "Name", *[e.capitalize() for e in emotions], "Samples", "Engagement %", "Level"],
           rows, pct_cols=[3 + len(emotions)])
    _about(wb, "Class monitoring report", [
        ("Subject", m["subject"]), ("Class", f'{m["department"]}-{m["semester"]}'),
        ("Started", m["started_at"]), ("Overall engagement", f'{m["overall_engagement"]}% ({m["level"]})')])
    wb.move_sheet("About", offset=-(len(wb.sheetnames) - 1))
    return wb

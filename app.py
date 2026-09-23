import os
import re
import sqlite3
from html import escape

from flask import Flask, Response, g, jsonify, request

BASE = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE, "data", "reportcard.db")
PASS_PERCENT = 33  # har subject me pass hone ke liye minimum %

app = Flask(__name__, static_folder="public", static_url_path="")

# ---------- SQL Database (SQLite, Python ke saath aata hai) ----------
SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_name    TEXT NOT NULL,
    roll_no         TEXT,
    class_name      TEXT,
    total           REAL NOT NULL,
    max_total       REAL NOT NULL,
    percentage      REAL NOT NULL,
    grade           TEXT NOT NULL,
    failed_subjects INTEGER NOT NULL,
    result          TEXT NOT NULL,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS subjects (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    marks     REAL NOT NULL,
    max       REAL NOT NULL,
    percent   REAL NOT NULL,
    grade     TEXT NOT NULL,
    status    TEXT NOT NULL
);
"""


def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.executescript(SCHEMA)
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def num(x):
    """80.0 ko 80 dikhane ke liye"""
    return int(x) if float(x).is_integer() else x


def grade_of(p):
    if p >= 90: return "A+"
    if p >= 80: return "A"
    if p >= 70: return "B+"
    if p >= 60: return "B"
    if p >= 50: return "C"
    if p >= PASS_PERCENT: return "D"
    return "F"


# Marks se total, percentage, pass/fail nikalna
def build_report(body):
    name = str(body.get("studentName") or "").strip()
    if not name:
        return None, "Student ka naam likhein."
    raw = body.get("subjects")
    if not isinstance(raw, list) or not raw:
        return None, "Kam se kam 1 subject chahiye."

    subjects = []
    for s in raw:
        sname = str(s.get("name") or "").strip()
        try:
            marks = float(s.get("marks"))
            mx = float(s.get("max") or 100)
        except (TypeError, ValueError):
            return None, f"{sname or 'Subject'}: marks sahi likhein."
        if not sname:
            return None, "Har subject ka naam likhein."
        if marks < 0 or mx <= 0:
            return None, f"{sname}: marks sahi likhein."
        if marks > mx:
            return None, f"{sname}: marks {num(mx)} se zyada nahi ho sakte."
        pct = round(marks / mx * 100, 2)
        subjects.append({"name": sname, "marks": marks, "max": mx, "percent": pct,
                         "grade": grade_of(pct), "status": "PASS" if pct >= PASS_PERCENT else "FAIL"})

    total = sum(s["marks"] for s in subjects)
    max_total = sum(s["max"] for s in subjects)
    percentage = round(total / max_total * 100, 2)
    failed = sum(1 for s in subjects if s["status"] == "FAIL")
    return {
        "studentName": name,
        "rollNo": str(body.get("rollNo") or "").strip(),
        "className": str(body.get("className") or "").strip(),
        "subjects": subjects, "total": total, "maxTotal": max_total,
        "percentage": percentage, "grade": grade_of(percentage),
        "failedSubjects": failed, "result": "PASS" if failed == 0 else "FAIL",
    }, None


def get_report(rid):
    db = get_db()
    r = db.execute("SELECT * FROM reports WHERE id = ?", (rid,)).fetchone()
    if r is None:
        return None
    subs = db.execute(
        "SELECT name, marks, max, percent, grade, status FROM subjects WHERE report_id = ? ORDER BY id", (rid,)
    ).fetchall()
    return {
        "id": str(r["id"]), "studentName": r["student_name"], "rollNo": r["roll_no"] or "",
        "className": r["class_name"] or "",
        "subjects": [{**dict(s), "marks": num(s["marks"]), "max": num(s["max"])} for s in subs],
        "total": num(r["total"]), "maxTotal": num(r["max_total"]), "percentage": r["percentage"],
        "grade": r["grade"], "failedSubjects": r["failed_subjects"], "result": r["result"],
        "createdAt": r["created_at"],
    }


# Report + uske subjects ko ek saath save karna (transaction)
def save_report(d, rid=None):
    db = get_db()
    with db:
        if rid:
            db.execute(
                "UPDATE reports SET student_name=?, roll_no=?, class_name=?, total=?, max_total=?, "
                "percentage=?, grade=?, failed_subjects=?, result=? WHERE id=?",
                (d["studentName"], d["rollNo"], d["className"], d["total"], d["maxTotal"],
                 d["percentage"], d["grade"], d["failedSubjects"], d["result"], rid))
            db.execute("DELETE FROM subjects WHERE report_id = ?", (rid,))
        else:
            cur = db.execute(
                "INSERT INTO reports (student_name, roll_no, class_name, total, max_total, percentage, "
                "grade, failed_subjects, result) VALUES (?,?,?,?,?,?,?,?,?)",
                (d["studentName"], d["rollNo"], d["className"], d["total"], d["maxTotal"],
                 d["percentage"], d["grade"], d["failedSubjects"], d["result"]))
            rid = cur.lastrowid
        db.executemany(
            "INSERT INTO subjects (report_id, name, marks, max, percent, grade, status) VALUES (?,?,?,?,?,?,?)",
            [(rid, s["name"], s["marks"], s["max"], s["percent"], s["grade"], s["status"]) for s in d["subjects"]])
    return rid


# ---------- Report card ka HTML (view aur download dono me) ----------
REPORT_CSS = """*{box-sizing:border-box}body{margin:0;background:#e9e6df;font-family:Georgia,'Times New Roman',serif;color:#1c2540;padding:24px}
.card{max-width:780px;margin:auto;background:#fffdf8;border:3px double #1c2540;padding:32px;position:relative}
h1{margin:0;text-align:center;font-size:30px;letter-spacing:1px}
.sub{text-align:center;margin:4px 0 22px;color:#5b6480;font-style:italic}
.info{display:flex;flex-wrap:wrap;gap:8px 32px;border-top:1px solid #1c2540;border-bottom:1px solid #1c2540;padding:12px 0;margin-bottom:20px}
.info div{flex:1 1 180px}.info b{display:block;font-size:12px;color:#5b6480;font-weight:normal}
table{width:100%;border-collapse:collapse;font-size:15px}
th{background:#1c2540;color:#fffdf8;padding:9px 6px;font-weight:normal}
td{padding:9px 6px;text-align:center;border-bottom:1px solid #d8d3c4}td.l{text-align:left}
tr.bad td{background:#fdeeee}.st{font-weight:bold}.st.PASS{color:#1f7a45}.st.FAIL{color:#b3261e}
.sum{display:flex;flex-wrap:wrap;gap:12px;margin-top:22px}
.box{flex:1 1 120px;border:1px solid #1c2540;padding:10px;text-align:center}
.box b{display:block;font-size:24px}.box span{font-size:12px;color:#5b6480}
.res{margin-top:22px;text-align:center;font-size:26px;font-weight:bold;letter-spacing:4px;padding:12px;border:3px solid}
.res.PASS{color:#1f7a45;border-color:#1f7a45}.res.FAIL{color:#b3261e;border-color:#b3261e}
.sign{display:flex;justify-content:space-between;margin-top:48px;font-size:13px;color:#5b6480}
.sign div{border-top:1px solid #1c2540;padding-top:4px;width:150px;text-align:center}
@media print{body{background:#fff;padding:0}}
"""


def report_html(r):
    rows = ""
    for i, s in enumerate(r["subjects"], 1):
        rows += (f'<tr class="{"bad" if s["status"] == "FAIL" else ""}"><td>{i}</td>'
                 f'<td class="l">{escape(s["name"])}</td><td>{s["marks"]}</td><td>{s["max"]}</td>'
                 f'<td>{s["percent"]}%</td><td>{s["grade"]}</td><td class="st {s["status"]}">{s["status"]}</td></tr>')
    return f"""<!DOCTYPE html><html lang="hi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Report Card - {escape(r["studentName"])}</title><style>{REPORT_CSS}</style></head><body><div class="card">
<h1>REPORT CARD</h1><p class="sub">Academic Progress Report</p>
<div class="info"><div><b>Student</b>{escape(r["studentName"])}</div><div><b>Roll No.</b>{escape(r["rollNo"] or "-")}</div><div><b>Class</b>{escape(r["className"] or "-")}</div></div>
<table><thead><tr><th>#</th><th>Subject</th><th>Marks</th><th>Out of</th><th>%</th><th>Grade</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table>
<div class="sum"><div class="box"><b>{r["total"]}/{r["maxTotal"]}</b><span>Total marks</span></div><div class="box"><b>{r["percentage"]}%</b><span>Percentage</span></div><div class="box"><b>{r["grade"]}</b><span>Grade</span></div><div class="box"><b>{r["failedSubjects"]}</b><span>Failed subjects</span></div></div>
<div class="res {r["result"]}">{r["result"]}</div>
<div class="sign"><div>Class Teacher</div><div>Principal</div></div>
</div></body></html>"""


# ---------- Pages ----------
@app.get("/")
def home():
    return app.send_static_file("index.html")


# ---------- API ----------
@app.get("/api/reports")
def list_reports():
    ids = [row["id"] for row in get_db().execute("SELECT id FROM reports ORDER BY id")]
    return jsonify([get_report(i) for i in ids])


@app.post("/api/reports")
def create_report():
    data, error = build_report(request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400
    return jsonify(get_report(save_report(data))), 201


@app.put("/api/reports/<int:rid>")
def update_report(rid):
    if get_report(rid) is None:
        return jsonify({"error": "Report nahi mila."}), 404
    data, error = build_report(request.get_json(silent=True) or {})
    if error:
        return jsonify({"error": error}), 400
    save_report(data, rid)
    return jsonify(get_report(rid))


@app.delete("/api/reports/<int:rid>")
def delete_report(rid):
    db = get_db()
    with db:
        cur = db.execute("DELETE FROM reports WHERE id = ?", (rid,))
    if cur.rowcount == 0:
        return jsonify({"error": "Report nahi mila."}), 404
    return jsonify({"ok": True})


@app.get("/api/reports/<int:rid>/view")
def view_report(rid):
    r = get_report(rid)
    if r is None:
        return "Report nahi mila.", 404
    return Response(report_html(r), mimetype="text/html")


@app.get("/api/reports/<int:rid>/download")
def download_report(rid):
    r = get_report(rid)
    if r is None:
        return "Report nahi mila.", 404
    fname = "report-card-" + re.sub(r"[^a-z0-9]+", "-", r["studentName"].lower()).strip("-") + ".html"
    return Response(report_html(r), mimetype="text/html",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Server chal raha hai: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)

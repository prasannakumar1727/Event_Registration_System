"""Table structures and all SQL queries (always parameterised)."""
import secrets
import string

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL CHECK (length(title) BETWEEN 3 AND 120),
    category    TEXT NOT NULL CHECK (category IN ('Workshop','Seminar','Hackathon','Conference')),
    description TEXT NOT NULL,
    schedule    TEXT NOT NULL DEFAULT '',
    event_date  TEXT NOT NULL,
    event_time  TEXT NOT NULL,
    venue       TEXT NOT NULL,
    seat_limit  INTEGER NOT NULL CHECK (seat_limit > 0),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);
CREATE TABLE IF NOT EXISTS registrations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    reg_code      TEXT NOT NULL UNIQUE,
    event_id      INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL,
    phone         TEXT NOT NULL,
    college       TEXT NOT NULL DEFAULT '',
    ticket_type   TEXT NOT NULL DEFAULT 'General' CHECK (ticket_type IN ('General','Student','VIP')),
    status        TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed','cancelled')),
    checked_in    INTEGER NOT NULL DEFAULT 0 CHECK (checked_in IN (0,1)),
    registered_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
    UNIQUE (event_id, email)
);
CREATE INDEX IF NOT EXISTS idx_reg_event_status ON registrations (event_id, status);
CREATE INDEX IF NOT EXISTS idx_reg_email ON registrations (email);
CREATE TABLE IF NOT EXISTS organizers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);
"""

EVENT_SELECT = """
SELECT e.*, (SELECT COUNT(*) FROM registrations r
             WHERE r.event_id = e.id AND r.status = 'confirmed') AS registered
FROM events e
"""
_ALPHABET = string.ascii_uppercase + string.digits


def new_reg_code():
    return "EVT-" + "".join(secrets.choice(_ALPHABET) for _ in range(8))


def event_dict(row):
    d = dict(row)
    d["date"] = d.pop("event_date")
    d["time"] = d.pop("event_time")
    d["schedule"] = [s for s in d["schedule"].split("\n") if s]
    d["available"] = max(d["seat_limit"] - d["registered"], 0)
    d["is_full"] = d["registered"] >= d["seat_limit"]
    return d


def list_events(db, category=None):
    sql, args = EVENT_SELECT, []
    if category:
        sql += " WHERE e.category = ?"
        args.append(category)
    rows = db.execute(sql + " ORDER BY e.event_date, e.event_time", args).fetchall()
    return [event_dict(r) for r in rows]


def get_event(db, event_id):
    row = db.execute(EVENT_SELECT + " WHERE e.id = ?", (event_id,)).fetchone()
    return event_dict(row) if row else None


def create_event(db, c):
    cur = db.execute(
        "INSERT INTO events (title, category, description, schedule, event_date, event_time, venue, seat_limit)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (c["title"], c["category"], c["description"], c["schedule"], c["date"], c["time"], c["venue"], c["seat_limit"]))
    return cur.lastrowid


def update_event(db, event_id, c):
    db.execute(
        "UPDATE events SET title=?, category=?, description=?, schedule=?, event_date=?, event_time=?,"
        " venue=?, seat_limit=? WHERE id=?",
        (c["title"], c["category"], c["description"], c["schedule"], c["date"], c["time"], c["venue"],
         c["seat_limit"], event_id))


def create_registration(db, event_id, c):
    """Seat-safe registration.

    BEGIN IMMEDIATE takes SQLite's write lock *before* the seat count is read, so two
    simultaneous requests can never both see the last free seat.
    Returns (status, payload) with status in: ok | not_found | duplicate | full.
    """
    db.execute("BEGIN IMMEDIATE")
    try:
        event = db.execute("SELECT id, seat_limit FROM events WHERE id = ?", (event_id,)).fetchone()
        if not event:
            db.execute("ROLLBACK")
            return "not_found", None
        existing = db.execute("SELECT id, status FROM registrations WHERE event_id = ? AND email = ?",
                              (event_id, c["email"])).fetchone()
        if existing and existing["status"] == "confirmed":
            db.execute("ROLLBACK")
            return "duplicate", None
        taken = db.execute("SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'confirmed'",
                           (event_id,)).fetchone()[0]
        if taken >= event["seat_limit"]:
            db.execute("ROLLBACK")
            return "full", None
        code = new_reg_code()
        while db.execute("SELECT 1 FROM registrations WHERE reg_code = ?", (code,)).fetchone():
            code = new_reg_code()
        if existing:  # re-registering after a cancellation re-uses the row (unique event+email)
            db.execute(
                "UPDATE registrations SET reg_code=?, name=?, phone=?, college=?, ticket_type=?, status='confirmed',"
                " checked_in=0, registered_at=strftime('%Y-%m-%d %H:%M:%S','now') WHERE id=?",
                (code, c["name"], c["phone"], c["college"], c["ticket_type"], existing["id"]))
            reg_id = existing["id"]
        else:
            reg_id = db.execute(
                "INSERT INTO registrations (reg_code, event_id, name, email, phone, college, ticket_type)"
                " VALUES (?,?,?,?,?,?,?)",
                (code, event_id, c["name"], c["email"], c["phone"], c["college"], c["ticket_type"])).lastrowid
        db.execute("COMMIT")
        return "ok", {"id": reg_id, "reg_code": code}
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise


def _like(q):
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def list_registrations(db, event_id=None, q=""):
    sql = ("SELECT r.*, e.title AS event_title FROM registrations r JOIN events e ON e.id = r.event_id"
           " WHERE 1=1")
    args = []
    if event_id is not None:
        sql += " AND r.event_id = ?"
        args.append(event_id)
    if q:
        sql += (" AND (r.name LIKE ? ESCAPE '\\' OR r.email LIKE ? ESCAPE '\\' OR r.phone LIKE ? ESCAPE '\\'"
                " OR r.college LIKE ? ESCAPE '\\' OR r.reg_code LIKE ? ESCAPE '\\')")
        args += [_like(q)] * 5
    rows = db.execute(sql + " ORDER BY r.registered_at DESC, r.id DESC", args).fetchall()
    return [dict(r) for r in rows]


def cancel_by_code(db, reg_code, email):
    row = db.execute("SELECT id, status FROM registrations WHERE reg_code = ? AND email = ?",
                     (reg_code, email)).fetchone()
    if not row:
        return "not_found"
    if row["status"] == "cancelled":
        return "already"
    db.execute("UPDATE registrations SET status='cancelled', checked_in=0 WHERE id = ?", (row["id"],))
    return "ok"


def totals(db):
    r = db.execute(
        "SELECT (SELECT COUNT(*) FROM events) AS events,"
        " (SELECT COUNT(*) FROM registrations WHERE status='confirmed') AS registrations,"
        " (SELECT COUNT(*) FROM registrations WHERE status='confirmed' AND checked_in=1) AS checked_in,"
        " (SELECT COALESCE(SUM(seat_limit),0) FROM events) AS seats").fetchone()
    d = dict(r)
    d["remaining"] = max(d["seats"] - d["registrations"], 0)
    return d

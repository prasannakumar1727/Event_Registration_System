"""Organizer API. Every route except login/logout is protected on the server."""
import csv
import io

from flask import Blueprint, Response, jsonify, request, session

from .. import auth, models
from ..database import get_db
from ..validators import clean_text, validate_event
from .public import fail, parse_id

bp = Blueprint("organizer", __name__, url_prefix="/organizer")


@bp.post("/login")
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return fail("Request body must be valid JSON.", 400)
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not isinstance(password, str) or not username.strip() or not password:
        return fail("Username and password are required.", 400)
    organizer = auth.verify_organizer(get_db(), username.strip()[:64], password[:200])
    if not organizer:
        return fail("Incorrect username or password.", 401)
    auth.login_user(organizer)
    return jsonify(success=True, message="Login successful.", username=organizer["username"])


@bp.post("/logout")
def logout():
    auth.logout_user()
    return jsonify(success=True, message="Logged out.")


@bp.get("/session")
@auth.login_required
def whoami():
    return jsonify(success=True, username=session.get("organizer_name"))


@bp.get("/events")
@auth.login_required
def events():
    db = get_db()
    return jsonify(success=True, events=models.list_events(db), totals=models.totals(db))


@bp.post("/events")
@auth.login_required
def add_event():
    cleaned, errors = validate_event(request.get_json(silent=True))
    if errors:
        return fail("Please correct the highlighted fields.", 400, errors)
    db = get_db()
    eid = models.create_event(db, cleaned)
    return jsonify(success=True, message="Event created.", event=models.get_event(db, eid)), 201


@bp.put("/events/<event_id>")
@auth.login_required
def edit_event(event_id):
    db = get_db()
    eid = parse_id(event_id)
    current = models.get_event(db, eid) if eid else None
    if not current:
        return fail("Event not found.", 404)
    cleaned, errors = validate_event(request.get_json(silent=True))
    if not errors and cleaned["seat_limit"] < current["registered"]:
        errors["seat_limit"] = f"Cannot be lower than the {current['registered']} seats already taken."
    if errors:
        return fail("Please correct the highlighted fields.", 400, errors)
    models.update_event(db, eid, cleaned)
    return jsonify(success=True, message="Event updated.", event=models.get_event(db, eid))


def _event_filter():
    """Returns (event_id, error_response). event_id None means 'all events'."""
    raw = request.args.get("event_id")
    if raw in (None, ""):
        return None, None
    eid = parse_id(raw)
    if eid is None:
        return None, fail("event_id must be a positive integer.", 400)
    if not models.get_event(get_db(), eid):
        return None, fail("Event not found.", 404)
    return eid, None


@bp.get("/registrations")
@auth.login_required
def registrations():
    eid, err = _event_filter()
    if err:
        return err
    q = clean_text(request.args.get("q", ""))[:100]
    db = get_db()
    rows = models.list_registrations(db, eid, q)
    body = {"success": True, "registrations": rows, "count": len(rows),
            "total": sum(1 for r in rows if r["status"] == "confirmed")}
    if eid:
        body["event"] = models.get_event(db, eid)
    return jsonify(body)


def _safe_cell(value):
    """Neutralise spreadsheet formula injection in exported CSV."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@bp.get("/export")
@auth.login_required
def export_csv():
    eid, err = _event_filter()
    if err:
        return err
    rows = models.list_registrations(get_db(), eid, clean_text(request.args.get("q", ""))[:100])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Registration ID", "Event", "Name", "Email", "Phone", "College", "Ticket", "Status",
                "Checked In", "Registered At (UTC)"])
    for r in rows:
        w.writerow([_safe_cell(x) for x in (r["reg_code"], r["event_title"], r["name"], r["email"], r["phone"],
                                            r["college"], r["ticket_type"], r["status"],
                                            "Yes" if r["checked_in"] else "No", r["registered_at"])])
    name = f"registrations_event_{eid}.csv" if eid else "registrations_all_events.csv"
    return Response("﻿" + buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _registration_or_404(reg_id):
    rid = parse_id(reg_id)
    row = get_db().execute("SELECT id, status FROM registrations WHERE id = ?", (rid,)).fetchone() if rid else None
    return row


@bp.post("/registrations/<reg_id>/checkin")
@auth.login_required
def checkin(reg_id):
    row = _registration_or_404(reg_id)
    if not row:
        return fail("Registration not found.", 404)
    if row["status"] != "confirmed":
        return fail("Cancelled registrations cannot be checked in.", 409)
    data = request.get_json(silent=True) or {}
    value = 1 if data.get("checked_in", True) else 0
    get_db().execute("UPDATE registrations SET checked_in = ? WHERE id = ?", (value, row["id"]))
    return jsonify(success=True, checked_in=bool(value))


@bp.post("/registrations/<reg_id>/cancel")
@auth.login_required
def cancel_registration(reg_id):
    row = _registration_or_404(reg_id)
    if not row:
        return fail("Registration not found.", 404)
    if row["status"] == "cancelled":
        return fail("Already cancelled.", 409)
    get_db().execute("UPDATE registrations SET status='cancelled', checked_in=0 WHERE id = ?", (row["id"],))
    return jsonify(success=True, message="Registration cancelled.")

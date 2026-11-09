"""Public API (events, registration, cancellation) and static frontend serving."""
from flask import Blueprint, current_app, jsonify, redirect, request, send_from_directory

from .. import auth, emailer, models
from ..database import get_db
from ..validators import CATEGORIES, validate_registration

bp = Blueprint("public", __name__)

PAGES = {"index.html", "event.html", "register.html", "success.html", "organizer_login.html"}


def fail(message, status, errors=None):
    body = {"success": False, "error": message}
    if errors:
        body["errors"] = errors
    return jsonify(body), status


def parse_id(value):
    try:
        n = int(value)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


@bp.get("/csrf-token")
def get_csrf():
    return jsonify(success=True, csrf_token=auth.csrf_token())


@bp.get("/events")
def events():
    category = request.args.get("category")
    if category and category not in CATEGORIES:
        return fail("Unknown category.", 400)
    return jsonify(success=True, events=models.list_events(get_db(), category))


@bp.get("/events/<event_id>")
def event_detail(event_id):
    eid = parse_id(event_id)
    event = models.get_event(get_db(), eid) if eid else None
    if not event:
        return fail("Event not found.", 404)
    return jsonify(success=True, event=event)


@bp.post("/register")
def register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return fail("Request body must be valid JSON.", 400)
    event_id = parse_id(data.get("event_id"))
    if event_id is None:
        return fail("A valid event_id is required.", 400, {"event_id": "A valid event is required."})
    cleaned, errors = validate_registration(data)
    if errors:
        return fail("Please correct the highlighted fields.", 400, errors)

    db = get_db()
    status, payload = models.create_registration(db, event_id, cleaned)
    if status == "not_found":
        return fail("Event not found.", 404)
    if status == "duplicate":
        return fail("You have already registered for this event with this email.", 409,
                    {"email": "This email is already registered for this event."})
    if status == "full":
        return fail("Event Full: no seats are left for this event.", 409)

    event = models.get_event(db, event_id)
    emailer.send_confirmation(event, payload, cleaned["email"], cleaned["name"])
    return jsonify(success=True, message="Registration successful!", registration={
        "id": payload["id"], "reg_code": payload["reg_code"], "event_id": event_id,
        "event_title": event["title"], "date": event["date"], "time": event["time"],
        "venue": event["venue"], "name": cleaned["name"], "email": cleaned["email"],
        "ticket_type": cleaned["ticket_type"]}), 201


@bp.post("/cancel")
def cancel():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return fail("Request body must be valid JSON.", 400)
    code = str(data.get("reg_code", "")).strip().upper()[:20]
    email = str(data.get("email", "")).strip().lower()[:254]
    if not code or not email:
        return fail("Registration ID and email are required.", 400)
    result = models.cancel_by_code(get_db(), code, email)
    if result == "not_found":
        return fail("No registration matches that ID and email.", 404)
    if result == "already":
        return fail("This registration is already cancelled.", 409)
    return jsonify(success=True, message="Registration cancelled. Your seat has been released.")


# ---- static frontend -------------------------------------------------------
@bp.get("/")
def home():
    return send_from_directory(current_app.config["FRONTEND_DIR"], "index.html")


@bp.get("/<path:filename>")
def frontend(filename):
    root = current_app.config["FRONTEND_DIR"]
    if filename == "organizer.html":  # protected page: server-side check
        if not auth.is_logged_in():
            return redirect("/organizer_login.html")
        return send_from_directory(root, filename)
    if filename in PAGES or filename.startswith(("css/", "js/", "assets/")):
        return send_from_directory(root, filename)
    return fail("Not found.", 404)

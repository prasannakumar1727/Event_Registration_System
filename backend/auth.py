"""Organizer authentication, session handling and CSRF protection."""
import hmac
import secrets
from functools import wraps

from flask import jsonify, redirect, request, session
from werkzeug.security import check_password_hash, generate_password_hash

# Used to spend the same hashing time when the username does not exist.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def hash_password(password):
    return generate_password_hash(password)


def verify_organizer(db, username, password):
    row = db.execute("SELECT id, username, password_hash FROM organizers WHERE username = ?",
                     (username,)).fetchone()
    ok = check_password_hash(row["password_hash"] if row else _DUMMY_HASH, password)
    return row if (row and ok) else None


def login_user(organizer):
    session.clear()  # prevents session fixation
    session["organizer_id"] = organizer["id"]
    session["organizer_name"] = organizer["username"]
    session.permanent = True


def logout_user():
    session.clear()


def is_logged_in():
    return "organizer_id" in session


def login_required(view):
    """API guard: JSON 401 when there is no organizer session."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_logged_in():
            return jsonify(success=False, error="Authentication required. Please log in as an organizer."), 401
        return view(*args, **kwargs)
    return wrapper


def page_login_required(view):
    """Page guard: redirect browsers to the login page."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_logged_in():
            return redirect("/organizer_login.html")
        return view(*args, **kwargs)
    return wrapper


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def csrf_guard():
    """before_request hook: every state-changing request must carry the session's CSRF token."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.headers.get("X-CSRF-Token", "")
        expected = session.get("csrf", "")
        if not expected or not hmac.compare_digest(sent, expected):
            return jsonify(success=False, error="Missing or invalid CSRF token. Refresh the page and try again."), 403
    return None

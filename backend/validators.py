"""Input validation helpers (used for every state-changing request).

All checks run on the server; the frontend repeats the same rules only for
quick feedback.  Functions return (cleaned_data, errors) where `errors` maps a
field name to a human-readable message.
"""
import re
from datetime import datetime

TICKET_TYPES = ("General", "Student", "VIP")
CATEGORIES = ("Workshop", "Seminar", "Hackathon", "Conference")

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^[1-9]\d{9}$")
COLLEGE_RE = re.compile(r"^[\w\s.,&'()/\-]+$", re.UNICODE)
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(value):
    """Trim, drop control characters and collapse repeated whitespace."""
    value = CONTROL_RE.sub("", value)
    return re.sub(r"\s+", " ", value).strip()


def _get_str(data, field, errors, required=True, max_len=100):
    raw = data.get(field)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if required:
            errors[field] = "This field is required."
        return ""
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        raw = str(raw)
    if not isinstance(raw, str):
        errors[field] = "Invalid value."
        return ""
    if len(raw) > max_len * 3:  # absurdly long input: reject before processing
        errors[field] = f"Must be at most {max_len} characters."
        return ""
    cleaned = clean_text(raw)
    if len(cleaned) > max_len:
        errors[field] = f"Must be at most {max_len} characters."
    return cleaned


def validate_registration(data):
    errors = {}
    if not isinstance(data, dict):
        return {}, {"_": "Request body must be a JSON object."}

    name = _get_str(data, "name", errors, max_len=60)
    if name and "name" not in errors:
        if not all(c.isalpha() or c in " .'-" for c in name):
            errors["name"] = "Name may contain only letters, spaces, dots, hyphens and apostrophes."
        elif sum(c.isalpha() for c in name) < 2:
            errors["name"] = "Name must contain at least 2 letters."

    email = _get_str(data, "email", errors, max_len=254).lower()
    if email and "email" not in errors:
        local = email.split("@")[0]
        if not EMAIL_RE.match(email) or ".." in email or len(local) > 64 or local.startswith("."):
            errors["email"] = "Enter a valid email address (e.g. name@example.com)."

    phone_raw = _get_str(data, "phone", errors, max_len=20)
    phone = re.sub(r"[\s\-]", "", phone_raw)
    if phone.startswith("+91"):
        phone = phone[3:]
    if phone and "phone" not in errors and not PHONE_RE.match(phone):
        errors["phone"] = "Phone must be exactly 10 digits (digits only)."

    college = _get_str(data, "college", errors, required=False, max_len=100)
    if college and "college" not in errors and not COLLEGE_RE.match(college):
        errors["college"] = "College contains invalid characters."

    ticket = _get_str(data, "ticket_type", errors, required=False, max_len=20) or "General"
    if "ticket_type" not in errors and ticket not in TICKET_TYPES:
        errors["ticket_type"] = "Ticket type must be one of: " + ", ".join(TICKET_TYPES) + "."

    cleaned = {"name": name, "email": email, "phone": phone, "college": college, "ticket_type": ticket}
    return cleaned, errors


def validate_event(data):
    errors = {}
    if not isinstance(data, dict):
        return {}, {"_": "Request body must be a JSON object."}

    title = _get_str(data, "title", errors, max_len=120)
    if title and len(title) < 3:
        errors["title"] = "Title must be at least 3 characters."
    category = _get_str(data, "category", errors, max_len=20)
    if category and category not in CATEGORIES:
        errors["category"] = "Category must be one of: " + ", ".join(CATEGORIES) + "."
    description = _get_str(data, "description", errors, max_len=2000)
    venue = _get_str(data, "venue", errors, max_len=120)

    date = _get_str(data, "date", errors, max_len=10)
    if date and "date" not in errors:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            errors["date"] = "Date must be in YYYY-MM-DD format."
    time = _get_str(data, "time", errors, max_len=5)
    if time and "time" not in errors and not TIME_RE.match(time):
        errors["time"] = "Time must be in 24-hour HH:MM format."

    seats = data.get("seat_limit")
    try:
        if isinstance(seats, bool) or seats in (None, ""):
            raise ValueError
        seats = int(seats)
        if not 1 <= seats <= 10000:
            raise ValueError
    except (TypeError, ValueError):
        errors["seat_limit"] = "Seat limit must be a whole number between 1 and 10000."
        seats = 0

    sched = data.get("schedule", "")
    lines = sched if isinstance(sched, list) else str(sched or "").splitlines()
    lines = [clean_text(str(x)) for x in lines if clean_text(str(x))]
    if len(lines) > 20 or any(len(x) > 120 for x in lines):
        errors["schedule"] = "At most 20 schedule lines of 120 characters each."

    cleaned = {"title": title, "category": category, "description": description, "venue": venue,
               "date": date, "time": time, "seat_limit": seats, "schedule": "\n".join(lines)}
    return cleaned, errors

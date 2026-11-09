"""Flask application factory.  Run with:  python -m backend.app"""
import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify

from . import auth
from .database import close_db, init_db
from .routes import organizer, public

ROOT = Path(__file__).resolve().parent.parent


def _secret_key():
    """SECRET_KEY from .env, else a random key generated once and kept in instance/ (git-ignored)."""
    key = os.getenv("SECRET_KEY")
    if key and key != "change-me":
        return key
    path = ROOT / "instance" / "secret_key.txt"
    if not path.exists():
        path.parent.mkdir(exist_ok=True)
        path.write_text(secrets.token_hex(32))
    return path.read_text().strip()


def create_app(test_config=None):
    load_dotenv(ROOT / ".env")
    app = Flask(__name__, static_folder=None)
    db_path = Path(os.getenv("DATABASE_PATH", "database/events.db"))
    app.config.update(
        DATABASE=str(db_path if db_path.is_absolute() else ROOT / db_path),
        FRONTEND_DIR=str(ROOT / "frontend"),
        ORGANIZER_USERNAME=os.getenv("ORGANIZER_USERNAME", "organizer"),
        ORGANIZER_PASSWORD=os.getenv("ORGANIZER_PASSWORD", "Organizer@123"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "0") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=2),
        MAX_CONTENT_LENGTH=64 * 1024,
        JSON_SORT_KEYS=False,
        SMTP_HOST=os.getenv("SMTP_HOST", ""),
        SMTP_PORT=int(os.getenv("SMTP_PORT", "587")),
        SMTP_USER=os.getenv("SMTP_USER", ""),
        SMTP_PASSWORD=os.getenv("SMTP_PASSWORD", ""),
        MAIL_FROM=os.getenv("MAIL_FROM", "events@example.com"),
    )
    if test_config:
        app.config.update(test_config)
    app.config.setdefault("SECRET_KEY", None)
    if not app.config["SECRET_KEY"]:
        app.config["SECRET_KEY"] = _secret_key()

    init_db(app)
    app.teardown_appcontext(close_db)
    app.before_request(auth.csrf_guard)
    app.register_blueprint(organizer.bp)
    app.register_blueprint(public.bp)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Content-Security-Policy",
                                "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        if resp.mimetype == "application/json":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    def json_error(message, status):
        return jsonify(success=False, error=message), status

    app.register_error_handler(404, lambda e: json_error("Not found.", 404))
    app.register_error_handler(405, lambda e: json_error("Method not allowed.", 405))
    app.register_error_handler(413, lambda e: json_error("Request too large.", 400))
    app.register_error_handler(500, lambda e: json_error("Internal server error.", 500))
    return app


if __name__ == "__main__":
    application = create_app()
    host, port = os.getenv("HOST", "127.0.0.1"), int(os.getenv("PORT", "5000"))
    print(f"\n  Event Registration System running at  http://{host}:{port}\n"
          f"  Organizer login page:                 http://{host}:{port}/organizer_login.html\n")
    application.run(host=host, port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")

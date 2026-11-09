# EventHub – Event Registration System

Full Stack Web Development · Week 4 internship project.
Browse events, register online with validation, and let organizers review participants from a protected dashboard.

## Features
- Public event listing with cards (image, date, time, venue, seats left), category filter and search
- Event detail page with description, schedule and Register button
- Registration form (name, email, phone, college, ticket type) with frontend **and** backend validation
- Unique registration ID (`EVT-XXXXXXXX`), confirmation page, duplicate prevention, "Event Full" detection
- Seat-safe registration using a SQLite `BEGIN IMMEDIATE` transaction (no overbooking, tested with 20 concurrent requests)
- Secure organizer login, protected dashboard, per-event stats, remaining-seat bars, participant search
- Optional features included: **CSV export, event create/edit, registration cancellation, check-in status, email-confirmation architecture** (console mailer by default, SMTP if configured)
- Responsive layout (mobile menu, scrollable tables, 44px tap targets)

## Technology stack
HTML5 · CSS3 (Grid/Flexbox) · Vanilla JavaScript · Python 3 · Flask · SQLite · Werkzeug password hashing · python-dotenv · pytest

## Folder structure
```
event-registration-system/
├── frontend/            index.html, event.html, register.html, success.html,
│                        organizer_login.html, organizer.html, css/, js/, assets/
├── backend/             app.py (factory) · models.py (schema+queries) · database.py
│                        auth.py · validators.py · emailer.py · routes/{public,organizer}.py
├── database/            seed_data.py (sample data) · events.db (auto-created, git-ignored)
├── tests/               test_api.py · test_cases.md
├── RUN_PROJECT.bat · RUN_TESTS.bat · requirements.txt · .env.example · pytest.ini
```

## Run on Windows 11 (PowerShell)
```powershell
Expand-Archive -Path .\Week_4_Event_Registration_System.zip -DestinationPath .
cd .\event-registration-system
.\RUN_PROJECT.bat        # creates venv, installs packages, creates + seeds DB, starts server
```
Open **http://127.0.0.1:5000**. Organizer login: **http://127.0.0.1:5000/organizer_login.html**

Manual alternative:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1      # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements.txt
python -m backend.app
```

## Demo organizer credentials (fictional, demo only)
| Username | Password |
|----------|----------|
| `organizer` | `Organizer@123` |

Stored only as a Werkzeug hash. Change them in `.env` (`ORGANIZER_USERNAME` / `ORGANIZER_PASSWORD`) **before the first launch**, or delete `database/events.db` to re-seed.

## Database schema
- **events**: `id` PK, `title`, `category`, `description`, `schedule`, `event_date`, `event_time`, `venue`, `seat_limit` (>0), `created_at`
- **registrations**: `id` PK, `reg_code` UNIQUE, `event_id` FK→events (cascade), `name`, `email`, `phone`, `college`, `ticket_type`, `status` (confirmed/cancelled), `checked_in`, `registered_at` (auto), **UNIQUE(event_id, email)**
- **organizers**: `id` PK, `username` UNIQUE, `password_hash`, `created_at`
- Indexes: `(event_id, status)`, `email`

## API
JSON everywhere: `{"success": true, ...}` or `{"success": false, "error": "...", "errors": {field: msg}}`.
State-changing requests need the header `X-CSRF-Token` (get it from `GET /csrf-token`).

| Method & path | Auth | Purpose | Codes |
|---|---|---|---|
| GET `/events` | – | List events with available seats | 200 |
| GET `/events/<id>` | – | Event details | 200, 404 |
| POST `/register` | – | Register `{event_id,name,email,phone,college,ticket_type}` | 201, 400, 404, 409 |
| POST `/cancel` | – | Cancel own registration `{reg_code,email}` | 200, 404, 409 |
| POST `/organizer/login` | – | Log in `{username,password}` | 200, 400, 401 |
| POST `/organizer/logout` | – | Log out | 200 |
| GET `/organizer/registrations?event_id=&q=` | Organizer | Participants + total | 200, 400, 401, 404 |
| GET `/organizer/events` | Organizer | Events with stats + totals | 200, 401 |
| POST `/organizer/events`, PUT `/organizer/events/<id>` | Organizer | Create / edit event | 200/201, 400, 401, 404 |
| GET `/organizer/export?event_id=` | Organizer | CSV download | 200, 401 |
| POST `/organizer/registrations/<id>/checkin` · `/cancel` | Organizer | Check-in / cancel | 200, 401, 404, 409 |

Example: `curl http://127.0.0.1:5000/events/1`

## Security implementation
Werkzeug password hashing (+ constant-time dummy hash for unknown users) · server-side signed, HttpOnly, SameSite=Lax sessions with 2-hour lifetime and session reset on login · CSRF token on every POST/PUT · every organizer API and the dashboard page checked on the server · parameterised SQL only (LIKE wildcards escaped) · strict server-side validation and input cleaning · frontend renders data with `textContent` (no `innerHTML`) · CSP and other security headers · CSV formula-injection guard · secret key from `.env` or auto-generated into git-ignored `instance/` · `.env` and the database are git-ignored.

## Testing
```powershell
.\RUN_TESTS.bat
# or
python -m pytest -v
```
34 automated tests (see `test_cases.md`). UI behaviour must be checked manually with the checklist in `test_cases.md`.

## Screenshots
Add your own after running the app (the PDF asks for desktop and mobile shots): save them in a `screenshots/` folder, then reference them here, e.g. `![Home](screenshots/home-desktop.png)`.

## Known limitations
- Emails are only logged to the console unless you configure SMTP in `.env` (SMTP path is untested).
- No login rate-limiting/lockout and a single organizer role.
- Flask's built-in development server is used; for production use a WSGI server (e.g. waitress) behind HTTPS and set `SESSION_COOKIE_SECURE=1`.
- The UI has not been tested in an automated browser; only the API and page serving are covered by tests.
- Anyone who knows a registration ID and its email can cancel it (no email verification).

## Upload to GitHub
```powershell
cd event-registration-system
git init
git add .
git commit -m "Week 4: Event Registration System"
git branch -M main
git remote add origin https://github.com/<your-username>/event-registration-system.git
git push -u origin main
```
(Create the empty repository on github.com first. `.env`, the database and `venv/` are excluded by `.gitignore`.)

"""Automated API tests.  Run:  python -m pytest -v"""
import threading

import pytest

from backend.app import create_app

GOOD = {"event_id": 1, "name": "Test Student", "email": "test.student@example.com",
        "phone": "9123456780", "college": "Demo College", "ticket_type": "Student"}
ORG = {"username": "organizer", "password": "Organizer@123"}


@pytest.fixture()
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db"), "SECRET_KEY": "test-secret"})


@pytest.fixture()
def client(app):
    return app.test_client()


def post(client, url, payload=None, method="post"):
    token = client.get("/csrf-token").get_json()["csrf_token"]
    return getattr(client, method)(url, json=payload, headers={"X-CSRF-Token": token})


def login(client, creds=ORG):
    return post(client, "/organizer/login", creds)


def reg(client, **over):
    return post(client, "/register", {**GOOD, **over})


def new_event(client, seats=2, title="Tiny Test Event"):
    r = post(client, "/organizer/events", {"title": title, "category": "Workshop", "description": "d",
                                           "venue": "Room 1", "date": "2027-03-01", "time": "10:00",
                                           "seat_limit": seats, "schedule": "10:00 | Start"})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["event"]["id"]


# ---------------- official PDF test cases ----------------
def test_TC_EVENT_01_valid_registration(client):
    r = reg(client)
    body = r.get_json()
    assert r.status_code == 201 and body["success"]
    assert body["registration"]["reg_code"].startswith("EVT-")
    login(client)
    rows = client.get("/organizer/registrations?event_id=1").get_json()["registrations"]
    assert any(x["email"] == GOOD["email"] for x in rows)  # record was saved


def test_TC_EVENT_02_invalid_email(client):
    before = client.get("/events/1").get_json()["event"]["registered"]
    for bad in ["not-an-email", "a@b", "a@@b.com", "a b@c.com", "x@y..com"]:
        r = reg(client, email=bad)
        assert r.status_code == 400 and "email" in r.get_json()["errors"], bad
    assert client.get("/events/1").get_json()["event"]["registered"] == before


def test_TC_EVENT_03_duplicate_registration(client):
    assert reg(client).status_code == 201
    r = reg(client, email="TEST.Student@Example.com")  # case-insensitive duplicate
    assert r.status_code == 409 and "already registered" in r.get_json()["error"]


def test_TC_EVENT_04_event_full(client):
    login(client)
    eid = new_event(client, seats=2)
    post(client, "/organizer/logout")
    assert reg(client, event_id=eid, email="a1@example.com").status_code == 201
    assert reg(client, event_id=eid, email="a2@example.com").status_code == 201
    r = reg(client, event_id=eid, email="a3@example.com")
    assert r.status_code == 409 and "Event Full" in r.get_json()["error"]
    assert client.get(f"/events/{eid}").get_json()["event"]["is_full"] is True


def test_TC_EVENT_05_dashboard_without_login(client):
    page = client.get("/organizer.html")
    assert page.status_code == 302 and page.headers["Location"].endswith("/organizer_login.html")
    assert client.get("/organizer/registrations?event_id=1").status_code == 401


def test_TC_EVENT_06_organizer_views_registrations(client):
    login(client)
    r = client.get("/organizer/registrations?event_id=1")
    body = r.get_json()
    assert r.status_code == 200
    assert body["total"] == 12 and len(body["registrations"]) == 12  # seed data: 12 for AI Workshop
    assert body["event"]["registered"] == 12 and body["event"]["available"] == 88


# ---------------- additional QA ----------------
def test_events_list_and_detail(client):
    r = client.get("/events")
    events = r.get_json()["events"]
    assert r.status_code == 200 and 5 <= len(events) <= 8
    assert {"title", "date", "time", "venue", "available"} <= set(events[0])
    assert client.get("/events/1").status_code == 200


@pytest.mark.parametrize("eid", ["9999", "abc", "-1", "0"])
def test_invalid_event_id(client, eid):
    assert client.get(f"/events/{eid}").status_code == 404


def test_register_unknown_event(client):
    assert reg(client, event_id=9999).status_code == 404
    assert reg(client, event_id="abc").status_code == 400


def test_empty_required_fields(client):
    r = post(client, "/register", {"event_id": 1, "name": "", "email": "", "phone": ""})
    errs = r.get_json()["errors"]
    assert r.status_code == 400 and {"name", "email", "phone"} <= set(errs)


@pytest.mark.parametrize("phone", ["12345", "abcdefghij", "0123456789", "98765432101", "98765-4321x"])
def test_invalid_phone(client, phone):
    r = reg(client, phone=phone)
    assert r.status_code == 400 and "phone" in r.get_json()["errors"]


def test_very_long_input(client):
    r = reg(client, name="A" * 5000, college="C" * 5000, email="a" * 300 + "@example.com")
    assert r.status_code == 400
    assert {"name", "college", "email"} <= set(r.get_json()["errors"])


@pytest.mark.parametrize("payload", ["<script>alert(1)</script>", "Robert'); DROP TABLE registrations;--",
                                     "' OR '1'='1"])
def test_malicious_input_rejected_and_db_intact(client, payload):
    assert reg(client, name=payload).status_code == 400
    assert reg(client, college=payload).status_code == 400
    assert client.get("/events").status_code == 200  # tables still exist


def test_sql_injection_in_search_and_ids(client):
    login(client)
    r = client.get("/organizer/registrations?q=%27%20OR%201%3D1%20--")
    assert r.status_code == 200 and r.get_json()["count"] == 0
    assert client.get("/organizer/registrations?event_id=1%20OR%201%3D1").status_code == 400


def test_wrong_and_correct_login(client):
    assert login(client, {"username": "organizer", "password": "wrong"}).status_code == 401
    assert login(client, {"username": "nobody", "password": "x"}).status_code == 401
    assert login(client, {"username": "", "password": ""}).status_code == 400
    assert login(client).status_code == 200
    assert client.get("/organizer/session").status_code == 200
    assert client.get("/organizer.html").status_code == 200
    post(client, "/organizer/logout")
    assert client.get("/organizer/session").status_code == 401


def test_password_is_hashed(app):
    import sqlite3
    h = sqlite3.connect(app.config["DATABASE"]).execute("SELECT password_hash FROM organizers").fetchone()[0]
    assert "Organizer@123" not in h and h.startswith(("scrypt:", "pbkdf2:"))


def test_unauthorized_api_access(client):
    for method, url in [("get", "/organizer/events"), ("get", "/organizer/registrations"),
                        ("get", "/organizer/export"), ("get", "/organizer/session")]:
        assert getattr(client, method)(url).status_code == 401, url
    for url, m in [("/organizer/events", "post"), ("/organizer/events/1", "put"),
                   ("/organizer/registrations/1/checkin", "post"), ("/organizer/registrations/1/cancel", "post")]:
        assert post(client, url, {}, m).status_code == 401, url


def test_csrf_required(client):
    assert client.post("/register", json=GOOD).status_code == 403
    assert client.post("/organizer/login", json=ORG, headers={"X-CSRF-Token": "forged"}).status_code == 403


def test_csv_export(client):
    login(client)
    r = client.get("/organizer/export?event_id=1")
    text = r.get_data(as_text=True)
    assert r.status_code == 200 and r.mimetype == "text/csv"
    assert "attachment" in r.headers["Content-Disposition"]
    assert text.lstrip("﻿").startswith("Registration ID,Event,Name") and len(text.strip().splitlines()) == 13


def test_search_filters_participants(client):
    login(client)
    body = client.get("/organizer/registrations?event_id=1&q=priya").get_json()
    assert body["count"] >= 1 and all("priya" in r["name"].lower() for r in body["registrations"])


def test_event_create_edit_validation(client):
    login(client)
    assert post(client, "/organizer/events", {"title": "x"}).status_code == 400
    eid = new_event(client, seats=3)
    assert post(client, f"/organizer/events/{eid}", {}, "put").status_code == 400
    reg(client, event_id=eid, email="e1@example.com")
    reg(client, event_id=eid, email="e2@example.com")
    body = {"title": "Renamed Event", "category": "Seminar", "description": "d", "venue": "V",
            "date": "2027-03-02", "time": "11:30", "seat_limit": 1}
    assert post(client, f"/organizer/events/{eid}", body, "put").status_code == 400  # below taken seats
    body["seat_limit"] = 10
    r = post(client, f"/organizer/events/{eid}", body, "put")
    assert r.status_code == 200 and r.get_json()["event"]["title"] == "Renamed Event"


def test_checkin_and_cancel_flow(client):
    code = reg(client).get_json()["registration"]
    login(client)
    rid = code["id"]
    assert post(client, f"/organizer/registrations/{rid}/checkin", {"checked_in": True}).status_code == 200
    assert post(client, f"/organizer/registrations/{rid}/cancel").status_code == 200
    assert post(client, f"/organizer/registrations/{rid}/checkin", {}).status_code == 409
    assert post(client, "/organizer/registrations/99999/cancel").status_code == 404


def test_public_cancel_releases_seat_and_allows_reregister(client):
    login(client)
    eid = new_event(client, seats=1)
    post(client, "/organizer/logout")
    first = reg(client, event_id=eid).get_json()["registration"]
    assert reg(client, event_id=eid, email="other@example.com").status_code == 409  # full
    assert post(client, "/cancel", {"reg_code": first["reg_code"], "email": GOOD["email"]}).status_code == 200
    assert post(client, "/cancel", {"reg_code": first["reg_code"], "email": GOOD["email"]}).status_code == 409
    assert post(client, "/cancel", {"reg_code": "EVT-NOPE", "email": GOOD["email"]}).status_code == 404
    assert reg(client, event_id=eid, email="other@example.com").status_code == 201  # seat was freed


def test_persistence_after_restart(tmp_path):
    cfg = {"TESTING": True, "DATABASE": str(tmp_path / "persist.db"), "SECRET_KEY": "k"}
    c1 = create_app(cfg).test_client()
    assert reg(c1, email="persist@example.com").status_code == 201
    c2 = create_app(cfg).test_client()  # simulates a server restart on the same DB file
    login(c2)
    rows = c2.get("/organizer/registrations?event_id=1&q=persist@example.com").get_json()["registrations"]
    assert len(rows) == 1
    assert len(c2.get("/events").get_json()["events"]) == 7  # not re-seeded / duplicated


def test_concurrent_registrations_never_overbook(tmp_path):
    cfg = {"TESTING": True, "DATABASE": str(tmp_path / "race.db"), "SECRET_KEY": "k"}
    app = create_app(cfg)
    admin = app.test_client()
    login(admin)
    eid = new_event(admin, seats=5)
    results, lock = [], threading.Lock()

    def worker(i):
        c = app.test_client()
        status = reg(c, event_id=eid, email=f"racer{i}@example.com").status_code
        with lock:
            results.append(status)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results.count(201) == 5 and results.count(409) == 15
    assert admin.get(f"/events/{eid}").get_json()["event"]["registered"] == 5

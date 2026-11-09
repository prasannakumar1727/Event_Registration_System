# Test Cases and Results

All automated tests live in `tests/test_api.py` (pytest). Last full run on this build: **34 passed, 0 failed** (`python -m pytest`, Python 3.13, Flask 3.1).
Frontend pages were verified to be served (HTTP 200) and the JavaScript passes a syntax check; **no automated browser (UI) tests were run** – the manual UI checklist below is for you to tick off during your demo.

## Official PDF test cases

| ID | Scenario | Expected | Automated test | Result |
|----|----------|----------|----------------|--------|
| TC_EVENT_01 | Register with valid details | Record saved, registration ID returned (201) | `test_TC_EVENT_01_valid_registration` | Pass |
| TC_EVENT_02 | Submit invalid email | 400, error on `email`, nothing saved | `test_TC_EVENT_02_invalid_email` | Pass |
| TC_EVENT_03 | Register twice, same email + event | 409 with clear message (case-insensitive) | `test_TC_EVENT_03_duplicate_registration` | Pass |
| TC_EVENT_04 | Register for a full event | 409 "Event Full", not saved | `test_TC_EVENT_04_event_full` | Pass |
| TC_EVENT_05 | Open organizer page without login | Redirect to login (302); API returns 401 | `test_TC_EVENT_05_dashboard_without_login` | Pass |
| TC_EVENT_06 | Organizer views registrations | Correct list and total count (200) | `test_TC_EVENT_06_organizer_views_registrations` | Pass |

## Additional automated tests

| Area | Test | Result |
|------|------|--------|
| Events API | `test_events_list_and_detail` | Pass |
| Invalid event ID (`9999`, `abc`, `-1`, `0`) | `test_invalid_event_id` (4 cases) | Pass |
| Unknown event on register (404) / bad id (400) | `test_register_unknown_event` | Pass |
| Empty required fields | `test_empty_required_fields` | Pass |
| Invalid phone (5 variants) | `test_invalid_phone` | Pass |
| Very long input | `test_very_long_input` | Pass |
| Special / malicious input (XSS, SQL) | `test_malicious_input_rejected_and_db_intact` (3 cases), `test_sql_injection_in_search_and_ids` | Pass |
| Wrong and correct organizer login, logout | `test_wrong_and_correct_login` | Pass |
| Password stored hashed | `test_password_is_hashed` | Pass |
| Unauthorized access to every organizer API | `test_unauthorized_api_access` | Pass |
| CSRF enforcement | `test_csrf_required` | Pass |
| CSV export | `test_csv_export` | Pass |
| Participant search | `test_search_filters_participants` | Pass |
| Event create / edit validation | `test_event_create_edit_validation` | Pass |
| Check-in and organizer cancel | `test_checkin_and_cancel_flow` | Pass |
| Public cancel frees seat, re-register | `test_public_cancel_releases_seat_and_allows_reregister` | Pass |
| Data persists after server restart | `test_persistence_after_restart` | Pass |
| 20 simultaneous requests, 5 seats – never overbooked | `test_concurrent_registrations_never_overbook` | Pass |

## Manual UI checklist (to run in a browser – not yet run by me)

- [ ] Home page lists 7 events; category chips and search filter the cards
- [ ] "Startup Pitch Night" shows **Event Full** and its Register button is disabled
- [ ] Event page shows description, schedule and Register button; `event.html?id=999` shows "not found"
- [ ] Registration form shows inline errors for bad name / email / phone; Submit disables while sending
- [ ] Success page shows the registration ID; Copy and Cancel buttons work
- [ ] Opening `/organizer.html` while logged out redirects to the login page
- [ ] Organizer logs in, sees KPIs, searches participants, checks in, exports CSV, creates/edits an event, logs out
- [ ] Layout works at mobile width (burger menu, scrollable tables)

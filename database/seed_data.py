"""Sample data (fictional only).  Runs automatically on first launch, or manually:

    python -m database.seed_data
"""
from werkzeug.security import generate_password_hash

EVENTS = [
    ("AI Workshop", "Workshop",
     "A hands-on introduction to machine learning. Build and train your first model with Python and scikit-learn, "
     "then learn how to evaluate and deploy it. Laptops required; no prior ML experience needed.",
     "09:30 | Registration & welcome\n10:00 | Keynote: AI in the real world\n11:00 | Hands-on lab: your first model\n"
     "13:00 | Lunch break\n14:00 | Lab 2: evaluating & improving models\n16:00 | Demo showcase & Q&A",
     "2026-12-05", "10:00", "Main Auditorium", 100),
    ("Full-Stack Web Bootcamp", "Workshop",
     "One intensive day covering HTML, CSS, JavaScript and Flask. Ship a small full-stack app with a database "
     "and authentication by the end of the session.",
     "09:00 | Setup & tooling\n10:00 | Frontend fundamentals\n12:30 | Lunch\n13:30 | Flask + SQLite backend\n"
     "16:00 | Deploy & review",
     "2026-12-12", "09:00", "Computer Lab 3", 40),
    ("Cybersecurity Awareness Seminar", "Seminar",
     "Industry experts discuss phishing, password hygiene, secure coding and careers in security, "
     "followed by a live attack-and-defend demonstration.",
     "15:00 | Welcome\n15:15 | Talk: the modern threat landscape\n16:00 | Live demo: phishing & defence\n"
     "16:45 | Panel & Q&A",
     "2026-12-18", "15:00", "Seminar Hall B", 150),
    ("Startup Pitch Night", "Seminar",
     "Student founders pitch to a panel of mentors and angel investors. Limited seating so the Q&A stays "
     "intimate.",
     "18:00 | Doors open\n18:30 | Pitches (8 teams)\n20:00 | Mentor feedback\n20:30 | Networking",
     "2026-12-20", "18:00", "Innovation Hub", 5),
    ("CodeSprint 24-Hour Hackathon", "Hackathon",
     "Form a team of up to four and build a working product in 24 hours around the theme 'Tech for Campus'. "
     "Mentors, snacks and prizes included.",
     "10:00 | Kick-off & theme reveal\n11:00 | Hacking begins\n22:00 | Mentor round\n"
     "Next day 10:00 | Final submissions\nNext day 11:00 | Judging & awards",
     "2027-01-09", "10:00", "Engineering Block, Hall A", 120),
    ("Data Science Datathon", "Hackathon",
     "Twelve hours, one real-world dataset. Clean it, model it and present your insights to a panel of judges.",
     "09:00 | Dataset release\n09:30 | Teams start\n15:00 | Check-in with mentors\n19:00 | Presentations\n"
     "20:00 | Results",
     "2027-01-16", "09:00", "Data Lab, Block C", 60),
    ("National Tech Conference 2027", "Conference",
     "A full-day conference with keynotes on cloud, AI and open source, plus parallel tracks and an expo hall.",
     "09:00 | Registration\n10:00 | Opening keynote\n11:30 | Parallel tracks\n14:00 | Expo & lunch\n"
     "16:00 | Closing keynote",
     "2027-02-06", "09:00", "Convention Centre", 300),
]

NAMES = ["Priya Sharma", "Arjun Mehta", "Sneha Iyer", "Rahul Verma", "Ananya Reddy", "Karthik Nair",
         "Divya Menon", "Vikram Singh", "Meera Pillai", "Rohan Gupta", "Ishita Das", "Aditya Rao"]
COLLEGES = ["Greenfield Institute of Technology", "Lakeside Engineering College", "Sunrise University",
            "Riverdale College of Science"]
TICKETS = ["General", "Student", "Student", "VIP"]


def seed(conn, organizer_username="organizer", organizer_password="Organizer@123"):
    from backend.models import new_reg_code  # imported lazily to avoid a circular import

    conn.execute("INSERT INTO organizers (username, password_hash) VALUES (?, ?)",
                 (organizer_username, generate_password_hash(organizer_password)))
    if conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]:
        return
    for title, cat, desc, sched, date, time, venue, seats in EVENTS:
        conn.execute("INSERT INTO events (title, category, description, schedule, event_date, event_time,"
                     " venue, seat_limit) VALUES (?,?,?,?,?,?,?,?)", (title, cat, desc, sched, date, time, venue, seats))
    ids = {r["title"]: r["id"] for r in conn.execute("SELECT id, title FROM events")}
    plan = {"AI Workshop": 12, "Full-Stack Web Bootcamp": 6, "Cybersecurity Awareness Seminar": 8,
            "Startup Pitch Night": 5, "CodeSprint 24-Hour Hackathon": 9}  # Pitch Night starts full (5/5)
    for title, count in plan.items():
        for i in range(count):
            name = NAMES[i % len(NAMES)]
            email = f"{name.lower().replace(' ', '.')}{i}@example.com"
            phone = str(9876540000 + ids[title] * 100 + i)
            conn.execute(
                "INSERT INTO registrations (reg_code, event_id, name, email, phone, college, ticket_type)"
                " VALUES (?,?,?,?,?,?,?)",
                (new_reg_code(), ids[title], name, email, phone, COLLEGES[i % len(COLLEGES)], TICKETS[i % len(TICKETS)]))


if __name__ == "__main__":
    from backend.app import create_app
    create_app()
    print("Database initialised (tables created and sample data seeded if empty).")

# Complaint Ticket Desk

A small hostel complaint application with a simple browser dashboard and a JSON API. Students can submit and track complaints; wardens can list, filter, and advance ticket statuses; administrators can view simple counts. It uses Flask and SQLite without a separate database server or frontend framework.

## Problem statement

Hostel complaints can be difficult to track when they are shared informally. This application gives each complaint a ticket ID, records its category and handler, and provides a clear status workflow.

## Technologies

- Python 3 and Flask for HTTP routes and JSON responses
- SQLite and SQL for persistent data and constraints
- Python `unittest` for automated tests

## Project structure

```text
complaint-ticket-desk/
├── app.py                 # Flask page, JSON routes, and request validation
├── database.py            # SQLite connections, setup, and queries
├── schema.sql             # Tables and status-transition trigger
├── requirements.txt       # Flask dependency
├── README.md
├── .gitignore
├── tests/test_app.py      # API tests using a temporary database
├── templates/index.html   # Browser dashboard
├── static/css/style.css   # Page styling
├── static/js/app.js       # Browser interactions with the JSON API
└── complaints.db          # Generated on startup; ignored by Git
```

Open `http://127.0.0.1:5000/` for the browser dashboard. The API remains available under `/api/`; `/api` shows its status and route list. The dashboard calls the same JSON API documented below.

## Database schema

`categories` stores a unique category name and the team that handles it. On an empty database, initialization inserts five example categories: Electricity, Plumbing, Internet, Cleaning, and Maintenance.

`tickets` stores the student, room, description, category, status, and timestamp. SQLite generates `ticket_id` automatically. A foreign key requires a real category, a CHECK constraint rejects blank descriptions and unknown statuses, and `raised_at` defaults to the current timestamp. Foreign keys are enabled on every connection.

A database trigger allows only `Open → In progress → Closed`. The API uses a transaction (`BEGIN IMMEDIATE`) and an update conditional on the previously read status. Competing wardens serialize at the write lock; after the first update commits, the next request sees the new status and receives HTTP 409 instead of advancing it twice.

## Install and run on Ubuntu

```bash
cd complaint-ticket-desk
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

The API listens on `http://127.0.0.1:5000`. The database and tables are created automatically on startup. Stop the server with Ctrl+C.

## API

JSON errors use the shape `{"error":"..."}`.

| Method and path | Purpose | Success |
|---|---|---|
| `GET /` | Browser dashboard | `200` HTML |
| `GET /api` | API status and available routes | `200` JSON |
| `GET /api/db-check` | Database status and row counts | `200` |
| `POST /api/categories` | Create category (`name`, `handler`) | `201`; duplicate is `409` |
| `GET /api/categories` | List categories | `200` |
| `GET /api/categories/<cat_id>` | Get one category | `200`; missing is `404` |
| `POST /api/tickets` | Submit (`cat_id`, `student_name`, `room_no`, `description`) | `201`; invalid category/input is `400` |
| `GET /api/tickets/<ticket_id>` | Track a ticket and see handler/status | `200`; missing is `404` |
| `GET /api/warden/tickets` | List tickets; optional `status` and/or `category_id` | `200` |
| `PATCH /api/warden/tickets/<ticket_id>/status` | Advance one status step | `200`; conflict/invalid step is `409` |
| `GET /api/reports/status` | Counts grouped by status (including zeroes) | `200` |
| `GET /api/reports/category` | Counts grouped by category, including empty categories | `200` |

### Try the endpoints with curl

Run these in a second terminal while `python app.py` is running. The POST responses contain IDs; use the returned IDs in later commands if they differ from the examples.

```bash
curl http://127.0.0.1:5000/
curl http://127.0.0.1:5000/api/db-check
curl http://127.0.0.1:5000/api/categories
curl http://127.0.0.1:5000/api/categories/1

curl -X POST http://127.0.0.1:5000/api/categories \
  -H 'Content-Type: application/json' \
  -d '{"name":"Security","handler":"Security Office"}'

curl -X POST http://127.0.0.1:5000/api/tickets \
  -H 'Content-Type: application/json' \
  -d '{"cat_id":1,"student_name":"Rahul Sharma","room_no":"A-204","description":"The ceiling fan is not working."}'

curl http://127.0.0.1:5000/api/tickets/1
curl 'http://127.0.0.1:5000/api/warden/tickets'
curl 'http://127.0.0.1:5000/api/warden/tickets?status=Open'
curl 'http://127.0.0.1:5000/api/warden/tickets?category_id=1'

curl -X PATCH http://127.0.0.1:5000/api/warden/tickets/1/status \
  -H 'Content-Type: application/json' -d '{"status":"In progress"}'
curl -X PATCH http://127.0.0.1:5000/api/warden/tickets/1/status \
  -H 'Content-Type: application/json' -d '{"status":"Closed"}'

curl http://127.0.0.1:5000/api/reports/status
curl http://127.0.0.1:5000/api/reports/category
```

`PATCH` only advances one step; call it once for each transition. Repeating a transition after another warden has advanced the ticket returns `409 Conflict`.

## Tests

The tests use Python's built-in `unittest` runner and create a disposable SQLite file, leaving the real `complaints.db` untouched:

```bash
source venv/bin/activate
python -m unittest discover -s tests -v
```

## Inspect SQLite

Install the SQLite CLI if required, then:

```bash
sqlite3 complaints.db
```

Useful commands inside the SQLite prompt:

```sql
.tables
.schema categories
.schema tickets
SELECT * FROM categories;
SELECT * FROM tickets;
SELECT status, COUNT(*) FROM tickets GROUP BY status;
.quit
```

The database file is ignored by Git. Do not commit it; it is generated automatically from `schema.sql`.

## Three-minute demo

1. Start the server and show `GET /` and `/api/db-check`.
2. List the example categories, then submit a complaint with `POST /api/tickets`; point out its generated ticket ID and `Open` status.
3. Track that ID with `GET /api/tickets/<id>` and show the category handler.
4. List warden tickets, advance the ticket to `In progress`, then to `Closed`.
5. Try to reopen it to show the conflict response, then display both reports.

## Viva questions to practice

1. **Why Flask?** It provides simple URL routing and JSON responses without a large framework.
2. **Why SQLite?** It stores this small project's data in one local file and needs no database server.
3. **What is a primary key?** A unique identifier for each row, such as `ticket_id`.
4. **How does a ticket reference its category?** `tickets.cat_id` is a foreign key to `categories.cat_id`.
5. **How is the foreign key enabled?** Every new SQLite connection runs `PRAGMA foreign_keys = ON`.
6. **Why use SQL placeholders?** They keep user values separate from SQL syntax and prevent SQL injection.
7. **How is a ticket ID generated?** SQLite assigns it through `INTEGER PRIMARY KEY AUTOINCREMENT`.
8. **How is a blank description rejected?** The API validates it and the table has a `CHECK(length(trim(description)) > 0)` constraint.
9. **Where does the submission time come from?** SQLite's `CURRENT_TIMESTAMP` default.
10. **What does `sqlite3.Row` do?** It lets query results be accessed by column name as well as position.
11. **Why use `pathlib`?** It builds a reliable database path independent of the shell's current directory.
12. **How are connections closed safely?** The `get_connection` context manager commits on success, rolls back on error, and closes in `finally`.
13. **What does `GROUP BY` do in the reports?** It groups rows by status or category so `COUNT()` can summarize each group.
14. **How do category reports include categories with no complaints?** A `LEFT JOIN` keeps every category; `COUNT(ticket_id)` is zero when there is no ticket.
15. **How are competing wardens handled?** `BEGIN IMMEDIATE` serializes writers; each transition checks the current status and only updates the expected old status.
16. **Why return HTTP 409?** It indicates the requested update conflicts with the ticket's current state, such as another warden already advancing it.
17. **Why use a test database?** Tests can create and destroy their own database without changing real project data.
18. **What is the trigger for?** It enforces allowed status changes inside SQLite, even if a write bypasses the Flask route.

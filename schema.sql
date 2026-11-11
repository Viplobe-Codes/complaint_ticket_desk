-- Complaint categories and tickets.
CREATE TABLE IF NOT EXISTS categories (
    cat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    handler TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cat_id INTEGER NOT NULL,
    student_name TEXT NOT NULL,
    room_no TEXT NOT NULL,
    description TEXT NOT NULL CHECK (length(trim(description)) > 0),
    status TEXT NOT NULL DEFAULT 'Open'
        CHECK (status IN ('Open', 'In progress', 'Closed')),
    raised_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cat_id) REFERENCES categories(cat_id)
);

-- Keep the workflow valid even if a ticket is changed outside the Flask API.
CREATE TRIGGER IF NOT EXISTS tickets_status_transition
BEFORE UPDATE OF status ON tickets
WHEN NOT (
    (OLD.status = 'Open' AND NEW.status = 'In progress') OR
    (OLD.status = 'In progress' AND NEW.status = 'Closed')
)
BEGIN
    SELECT RAISE(ABORT, 'invalid ticket status transition');
END;

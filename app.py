"""JSON API for the Complaint Ticket Desk."""

from threading import Lock

from flask import Flask, jsonify, render_template, request

from database import (
    add_category,
    add_ticket,
    get_category,
    get_category_report,
    get_connection,
    get_table_counts,
    get_ticket,
    get_tickets,
    get_status_report,
    initialize_database,
    list_categories,
    update_ticket_status,
)


APP_NAME = "Complaint Ticket Desk"
ALLOWED_STATUSES = ("Open", "In progress", "Closed")


def create_app(database_path=None, initialize=True):
    """Create the Flask app; an alternate path lets tests use a temporary DB."""
    app = Flask(__name__)
    app.config["DATABASE"] = database_path
    app.config["DATABASE_INITIALIZED"] = initialize
    initialization_lock = Lock()
    if initialize:
        initialize_database(database_path)

    @app.before_request
    def ensure_database_is_ready():
        # The module-level app delays setup until a request, so importing app.py
        # from tests does not create or modify the real project database.
        if not app.config["DATABASE_INITIALIZED"]:
            with initialization_lock:
                if not app.config["DATABASE_INITIALIZED"]:
                    initialize_database(database_path)
                    app.config["DATABASE_INITIALIZED"] = True

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(400)
    def bad_request(_error):
        return jsonify({"error": "Invalid request"}), 400

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"error": "Method not allowed for this path"}), 405

    @app.get("/")
    def welcome():
        return render_template("index.html")

    @app.get("/api")
    def api_welcome():
        return jsonify({
            "application": APP_NAME,
            "status": "running",
            "available_api": [
                "GET /api/db-check", "GET, POST /api/categories",
                "GET /api/categories/<cat_id>", "POST /api/tickets",
                "GET /api/tickets/<ticket_id>", "GET /api/warden/tickets",
                "PATCH /api/warden/tickets/<ticket_id>/status",
                "GET /api/reports/status", "GET /api/reports/category",
            ],
        })

    @app.get("/api/db-check")
    def database_check():
        counts = get_table_counts(database_path)
        return jsonify({"database": "accessible", **counts})

    @app.post("/api/categories")
    def create_category():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error("Request body must be a JSON object")
        name, handler = data.get("name"), data.get("handler")
        if not valid_text(name) or not valid_text(handler):
            return error("name and handler must be non-empty strings")
        try:
            category_id = add_category(name.strip(), handler.strip(), database_path)
        except ValueError:
            return error("A category with that name already exists", 409)
        return jsonify({"message": "Category created successfully", "cat_id": category_id}), 201

    @app.get("/api/categories")
    def categories():
        return jsonify(list_categories(database_path))

    @app.get("/api/categories/<int:cat_id>")
    def category_detail(cat_id):
        category = get_category(cat_id, database_path)
        if category is None:
            return error("Category not found", 404)
        return jsonify(category)

    @app.post("/api/tickets")
    def create_ticket():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return error("Request body must be a JSON object")
        cat_id = data.get("cat_id")
        if isinstance(cat_id, bool) or not isinstance(cat_id, int) or cat_id < 1:
            return error("cat_id must be a positive integer")
        for field in ("student_name", "room_no", "description"):
            if not valid_text(data.get(field)):
                return error(f"{field} must be a non-empty string")
        try:
            ticket_id = add_ticket(
                cat_id, data["student_name"].strip(), data["room_no"].strip(),
                data["description"].strip(), database_path,
            )
        except ValueError:
            return error("Category not found", 400)
        return jsonify({
            "message": "Complaint submitted successfully",
            "ticket_id": ticket_id,
            "status": "Open",
        }), 201

    @app.get("/api/tickets/<int:ticket_id>")
    def track_ticket(ticket_id):
        ticket = get_ticket(ticket_id, database_path)
        if ticket is None:
            return error("Ticket not found", 404)
        return jsonify(ticket)

    @app.get("/api/warden/tickets")
    def warden_tickets():
        status = request.args.get("status")
        category = request.args.get("category_id")
        if status is not None and status not in ALLOWED_STATUSES:
            return error("status must be Open, In progress, or Closed")
        category_id = None
        if category is not None:
            try:
                category_id = int(category)
                if category_id < 1:
                    raise ValueError
            except ValueError:
                return error("category_id must be a positive integer")
        return jsonify(get_tickets(status, category_id, database_path))

    @app.patch("/api/warden/tickets/<int:ticket_id>/status")
    def change_ticket_status(ticket_id):
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or data.get("status") not in ALLOWED_STATUSES:
            return error("status must be Open, In progress, or Closed")
        try:
            changed = update_ticket_status(ticket_id, data["status"], database_path)
        except LookupError:
            return error("Ticket not found", 404)
        except ValueError as exc:
            return error(str(exc), 409)
        return jsonify({"message": "Ticket status updated", "ticket_id": ticket_id, "status": changed})

    @app.get("/api/reports/status")
    def status_report():
        return jsonify(get_status_report(database_path))

    @app.get("/api/reports/category")
    def category_report():
        return jsonify(get_category_report(database_path))

    return app


def valid_text(value):
    """True for a non-empty string containing at least one non-space character."""
    return isinstance(value, str) and bool(value.strip())


def error(message, status=400):
    return jsonify({"error": message}), status


app = create_app(initialize=False)


if __name__ == "__main__":
    app.run(debug=True)

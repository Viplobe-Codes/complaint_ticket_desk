"""API tests using a fresh temporary SQLite database for each test."""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path

from app import create_app


class ComplaintTicketApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        self.app = create_app(self.database_path)
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()
        self.category_id = self.client.get("/api/categories").get_json()[0]["cat_id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def create_ticket(self, description="Fan is not working"):
        return self.client.post("/api/tickets", json={
            "cat_id": self.category_id,
            "student_name": "Rahul Sharma",
            "room_no": "A-204",
            "description": description,
        })

    def test_home_and_database_check(self):
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn(b"Report an issue", home.data)
        self.assertEqual(self.client.get("/api").status_code, 200)
        response = self.client.get("/api/db-check")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["categories"], 5)

    def test_category_create_duplicate_list_and_detail(self):
        created = self.client.post("/api/categories", json={
            "name": "Security", "handler": "Security Office"
        })
        self.assertEqual(created.status_code, 201)
        self.assertEqual(self.client.get("/api/categories").status_code, 200)
        cat_id = created.json["cat_id"]
        self.assertEqual(self.client.get(f"/api/categories/{cat_id}").json["name"], "Security")
        duplicate = self.client.post("/api/categories", json={
            "name": "Security", "handler": "Another Team"
        })
        self.assertEqual(duplicate.status_code, 409)

    def test_ticket_submission_validation_and_tracking(self):
        created = self.create_ticket()
        self.assertEqual(created.status_code, 201)
        ticket_id = created.json["ticket_id"]
        tracked = self.client.get(f"/api/tickets/{ticket_id}")
        self.assertEqual(tracked.status_code, 200)
        self.assertEqual(tracked.json["status"], "Open")
        self.assertEqual(tracked.json["category"], "Electricity")
        self.assertEqual(self.client.get("/api/tickets/999999").status_code, 404)
        self.assertEqual(self.create_ticket("   ").status_code, 400)
        invalid_category = self.client.post("/api/tickets", json={
            "cat_id": 9999, "student_name": "A", "room_no": "1", "description": "Issue"
        })
        self.assertEqual(invalid_category.status_code, 400)

    def test_warden_list_filters_and_status_workflow(self):
        ticket_id = self.create_ticket().json["ticket_id"]
        self.assertEqual(len(self.client.get("/api/warden/tickets").json), 1)
        self.assertEqual(len(self.client.get("/api/warden/tickets?status=Open").json), 1)
        self.assertEqual(len(self.client.get(
            f"/api/warden/tickets?category_id={self.category_id}"
        ).json), 1)

        endpoint = f"/api/warden/tickets/{ticket_id}/status"
        self.assertEqual(self.client.patch(endpoint, json={"status": "In progress"}).status_code, 200)
        self.assertEqual(self.client.patch(endpoint, json={"status": "Closed"}).status_code, 200)
        self.assertEqual(self.client.patch(endpoint, json={"status": "Open"}).status_code, 409)

    def test_invalid_transition_and_conflicting_update(self):
        ticket_id = self.create_ticket().json["ticket_id"]
        endpoint = f"/api/warden/tickets/{ticket_id}/status"
        self.assertEqual(self.client.patch(endpoint, json={"status": "Closed"}).status_code, 409)
        self.assertEqual(self.client.patch(endpoint, json={"status": "Pending"}).status_code, 400)

        # Two wardens trying to apply the same next step: the second request conflicts.
        self.assertEqual(self.client.patch(endpoint, json={"status": "In progress"}).status_code, 200)
        conflict = self.client.patch(endpoint, json={"status": "In progress"})
        self.assertEqual(conflict.status_code, 409)

    def test_simultaneous_status_updates_only_advance_once(self):
        ticket_id = self.create_ticket().json["ticket_id"]
        endpoint = f"/api/warden/tickets/{ticket_id}/status"
        start_together = Barrier(2)

        def update_once():
            with self.app.test_client() as client:
                start_together.wait()
                return client.patch(endpoint, json={"status": "In progress"}).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _number: update_once(), range(2)))
        self.assertCountEqual(results, [200, 409])
        self.assertEqual(self.client.get(f"/api/tickets/{ticket_id}").json["status"], "In progress")

    def test_reports_count_and_include_empty_categories(self):
        self.create_ticket()
        statuses = self.client.get("/api/reports/status").json
        self.assertEqual(statuses, {"Open": 1, "In progress": 0, "Closed": 0})
        category_report = self.client.get("/api/reports/category").json
        self.assertEqual(len(category_report), 5)
        self.assertIn({"category": "Plumbing", "total_tickets": 0}, category_report)


if __name__ == "__main__":
    unittest.main()

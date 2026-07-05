import tempfile
import unittest
from pathlib import Path

import app


class DiaryAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        app.configure_data_paths(Path(self.temp_dir.name))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_register_and_login_flow(self) -> None:
        ok, message, user = app.register_user("alice", "secret")
        self.assertTrue(ok)
        self.assertEqual(user["username"], "alice")
        authenticated = app.authenticate_user("alice", "secret")
        self.assertIsNotNone(authenticated)

    def test_entry_crud(self) -> None:
        _, _, user = app.register_user("bob", "secret")
        entry = app.create_entry(user["id"], "Morning", "Had a great day")
        self.assertEqual(entry["title"], "Morning")
        updated = app.update_entry(entry["id"], user["id"], "Morning", "Updated note")
        self.assertEqual(updated["content"], "Updated note")
        deleted = app.delete_entry(entry["id"], user["id"])
        self.assertTrue(deleted)
        self.assertEqual(app.list_entries(user["id"]), [])


if __name__ == "__main__":
    unittest.main()

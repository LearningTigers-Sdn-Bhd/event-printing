import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import config_store
from api_client import BackendAlreadyCheckedIn, BackendClient, BackendError


def _resp(status, body):
    r = mock.Mock(status_code=status, text=str(body))
    r.json.return_value = body
    return r


class NoPrintTypeTests(unittest.TestCase):
    def test_match_ignores_case_and_spaces(self):
        cfg = {"no_print_ticket_types": ["Staff", "Virtual Pass"]}
        self.assertTrue(config_store.is_no_print_type(" staff ", cfg))
        self.assertTrue(config_store.is_no_print_type("VIRTUAL PASS", cfg))
        self.assertFalse(config_store.is_no_print_type("Delegate", cfg))
        self.assertFalse(config_store.is_no_print_type("", cfg))
        self.assertFalse(config_store.is_no_print_type("Staff", {}))

    def test_empty_list_is_kept_empty(self):
        self.assertEqual(config_store._sanitize_no_print_types([]), [])
        self.assertEqual(config_store._sanitize_no_print_types("nope"), [])
        self.assertEqual(config_store._sanitize_no_print_types(["A", "a", " B "]), ["A", "B"])


class CheckIn422Tests(unittest.TestCase):
    def _check_in(self, body):
        with mock.patch("api_client.httpx.patch", return_value=_resp(422, body)):
            BackendClient("http://x", "key").check_in("T1")

    def test_already_scanned_carries_first_scan_details(self):
        with self.assertRaises(BackendAlreadyCheckedIn) as ctx:
            self._check_in({
                "error": "Ticket has already been checked in.",
                "checked_in_at": "2026-11-17T02:00:00Z",
                "blocked_by": {"scanned_by_name": "Aina", "location_name": "Hall A"},
            })
        self.assertEqual(ctx.exception.checked_in_at, "2026-11-17T02:00:00Z")
        self.assertEqual(ctx.exception.checked_in_by, "Aina")
        self.assertEqual(ctx.exception.location, "Hall A")

    def test_unpaid_is_an_error_not_a_reprintable_duplicate(self):
        with self.assertRaises(BackendError) as ctx:
            self._check_in({"error": "Ticket payment is still pending. Cannot check in until payment is confirmed."})
        self.assertNotIsInstance(ctx.exception, BackendAlreadyCheckedIn)
        self.assertIn("payment", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from models import TicketPayload


class TicketPayloadTests(unittest.TestCase):
    def test_top_level_organisation_maps_to_company(self):
        payload = TicketPayload(
            ticket_id="0899c238-5332-4e72-bffc-1bc3f0395e4b",
            name="Muhammad Irfan Bin Janis",
            organisation="Youth Care Malaysia ",
            ticket_type="Interested Delegate",
        )

        self.assertEqual(payload.company, "Youth Care Malaysia")


if __name__ == "__main__":
    unittest.main()

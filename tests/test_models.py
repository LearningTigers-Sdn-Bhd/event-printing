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

    def test_custom_values_sanitized(self):
        payload = TicketPayload(
            ticket_id="A1-0245",
            name="Test User",
            ticket_type="Visitor",
            custom={"Sponsor": " Acme Corp ", "": "dropped", "X" * 100: "too long key"},
        )

        self.assertEqual(payload.custom, {"Sponsor": "Acme Corp"})

    def test_custom_dict_values_unwrapped(self):
        payload = TicketPayload(
            ticket_id="A1-0245",
            name="Test User",
            ticket_type="Visitor",
            custom={"Sponsor": {"value": "Acme"}},
        )

        self.assertEqual(payload.custom, {"Sponsor": "Acme"})


if __name__ == "__main__":
    unittest.main()

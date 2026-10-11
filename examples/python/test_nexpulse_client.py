import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from nexpulse_client import NexPulseClient, NexPulseError


class Response:
    status = 202

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"status":"accepted","accepted_count":1}'


class NexPulseClientTests(unittest.TestCase):
    def setUp(self):
        self.client = NexPulseClient("https://nexpulse.example/api/v1/telemetry", "planner-prod", "pik_live_test")

    @patch("nexpulse_client.urlopen", return_value=Response())
    def test_sends_service_key_and_identifier(self, open_url):
        result = self.client.send("events", {"method": "GET", "endpoint": "/health"})
        self.assertEqual(result["status"], "accepted")
        request = open_url.call_args.args[0]
        self.assertEqual(request.get_header("X-ingest-key"), "pik_live_test")
        self.assertEqual(request.full_url, "https://nexpulse.example/api/v1/telemetry/events")
        self.assertEqual(json.loads(request.data)["service_id"], "planner-prod")

    def test_rejects_cross_service_identity_before_network_call(self):
        with patch("nexpulse_client.urlopen") as open_url:
            with self.assertRaisesRegex(ValueError, "must match"):
                self.client.send("events", {"service_id": "other-service", "method": "GET"})
            open_url.assert_not_called()

    @patch("nexpulse_client.urlopen")
    def test_401_message_never_includes_credential(self, open_url):
        open_url.side_effect = HTTPError("https://nexpulse.example", 401, "denied", {}, None)
        with self.assertRaises(NexPulseError) as context:
            self.client.send("events", {"method": "GET"})
        self.assertEqual(context.exception.status, 401)
        self.assertNotIn("pik_live_test", str(context.exception))

    def test_rejects_empty_or_oversized_batch(self):
        with self.assertRaises(ValueError):
            self.client.send("logs", [])
        with self.assertRaises(ValueError):
            self.client.send("logs", [{"message": "x"}] * 101)


if __name__ == "__main__":
    unittest.main()

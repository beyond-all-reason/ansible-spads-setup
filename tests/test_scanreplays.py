import gzip
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scanreplays import HEADER, ScriptParser, filename_time, read_replay, scan, utc_time


START = datetime(2026, 10, 25, tzinfo=timezone.utc)
END = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
SCRIPT = """
// The attendee occurs as a player, spectator, and unrelated option.
[GAME] {
  [MODOPTIONS] { note=[KILL]Mango; }
  [PLAYER0] { Name=[KILL]Mango; Spectator=0; Team=0; }
  [PLAYER1] { Name=Snoopa; Spectator=1; }
  [PLAYER2] { Name=Not[KILL]Mango; Spectator=0; }
}
"""


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def replay(self, name="unknown.sdfz", started=START, script=SCRIPT,
               header_size=352, version=5):
        text = script.encode()
        prefix = HEADER.pack(b"spring demofile\0", version, header_size,
                             b"recoil", bytes(range(16)), int(started.timestamp()),
                             len(text))
        data = prefix + bytes(header_size - HEADER.size) + text
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(data))
        return path

    def test_header_and_actual_players(self):
        path = self.replay(header_size=354)
        started, game_id, players = read_replay(path)
        self.assertEqual(started, START)
        self.assertEqual(game_id, bytes(range(16)).hex())
        self.assertEqual(players, ["[KILL]Mango", "Not[KILL]Mango"])

    def test_literal_matching_excludes_spectators_and_options(self):
        self.replay()
        for attendee in ("Snoopa", "Mango", "KILL", "[kill]mango"):
            with self.subTest(attendee=attendee):
                self.assertEqual(scan(self.root, START, END, {attendee})["matches"], [])

    def test_recursive_discovery_checksum_and_unknown_filename(self):
        path = self.replay("Host[EU1][001]/demos-server/unknown.sdfz")
        result = scan(self.root, START, END, {"[KILL]Mango"})
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["matches"]), 1)
        match = result["matches"][0]
        self.assertEqual(match["path"], str(path.resolve()))
        self.assertEqual(match["size"], path.stat().st_size)
        self.assertEqual(match["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(match["matching_players"], ["[KILL]Mango"])

    def test_inclusive_start_exclusive_end_and_header_validation(self):
        self.replay("at-start.sdfz", START)
        self.replay("at-end.sdfz", END)
        self.replay("2026-10-25_02-00-00-000_header-outside.sdfz", END)
        result = scan(self.root, START, END, {"[KILL]Mango"})
        self.assertEqual(len(result["matches"]), 1)
        self.assertTrue(result["matches"][0]["path"].endswith("at-start.sdfz"))

    def test_filename_formats_and_outside_prefilter(self):
        self.assertEqual(filename_time("20261025_000000_map.sdfz"), START)
        self.assertEqual(filename_time("2026-10-25_00-00-00_map.sdfz"), START)
        self.assertEqual(filename_time("2026-10-25_00-00-00-500_map.sdfz"),
                         START.replace(microsecond=500000))
        self.assertIsNone(filename_time("2026-99-25_00-00-00_map.sdfz"))
        (self.root / "2026-10-24_12-00-00_map.sdfz").write_bytes(b"not gzip")
        result = scan(self.root, START, END, {"[KILL]Mango"})
        self.assertEqual(result["files_seen"], 1)
        self.assertEqual(result["files_parsed"], 0)
        self.assertEqual(result["errors"], [])

    def test_candidate_errors_are_explicit(self):
        (self.root / "corrupt.sdfz").write_bytes(b"not gzip")
        self.replay("future.sdfz", version=6)
        self.replay("missing-flag.sdfz", script="[GAME]{[PLAYER0]{Name=Snoopa;}}")
        result = scan(self.root, START, END, {"Snoopa"})
        self.assertEqual(len(result["errors"]), 3)
        self.assertEqual(result["matches"], [])

    def test_truncated_header_and_setup(self):
        for data in (b"spring demofile\0", HEADER.pack(
                b"spring demofile\0", 5, 352, b"", bytes(16),
                int(START.timestamp()), 100) + bytes(52)):
            path = self.root / "truncated.sdfz"
            path.write_bytes(gzip.compress(data))
            with self.assertRaises(ValueError):
                read_replay(path)

    def test_comments_case_and_quoted_names(self):
        script = '/* comment */ [game] { [player0] { NAME="Snoopa"; SPECTATOR=0; } }'
        self.assertEqual(read_replay(self.replay(script=script))[2], ["Snoopa"])
        for invalid in ("[GAME]{", "[GAME]{[PLAYER0]{Name=x;Name=y;}}",
                        "[GAME]{}[GAME]{}"):
            with self.subTest(script=invalid), self.assertRaises(ValueError):
                ScriptParser(invalid).parse()

    def test_explicit_timezone_required(self):
        self.assertEqual(utc_time("2026-10-25T01:00:00+01:00"), START)
        with self.assertRaises(ValueError):
            utc_time("2026-10-25T01:00:00")
        with self.assertRaises(ValueError):
            scan(self.root / "missing", START, END, {"Snoopa"})

    def test_cli_manifest_and_invalid_inputs(self):
        self.replay()
        attendees = self.root / "attendees.txt"
        attendees.write_text("\ufeff[KILL]Mango\n\n", encoding="utf-8")
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "scanreplays.py"),
                   "--root", str(self.root), "--attendees", str(attendees),
                   "--start", START.isoformat(), "--end", END.isoformat()]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["matches"]), 1)
        attendees.write_text("\n")
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Attendee list is empty", result.stderr)


if __name__ == "__main__":
    unittest.main()

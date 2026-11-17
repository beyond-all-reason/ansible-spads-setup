#!/usr/bin/env python3
"""Find time/player-matching SPADS replays using only their header and setup script."""

import argparse
import gzip
import hashlib
import json
import os
import re
import struct
import sys
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO


HEADER = struct.Struct("<16sii256s16sQi")
MAX_HEADER = 4096
MAX_SCRIPT = 16 * 1024 * 1024
FILENAME_TIME = re.compile(
    r"^(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:-\d{3})?|\d{8}_\d{6})_"
)


@dataclass
class Section:
    values: dict[str, str] = field(default_factory=dict)
    sections: dict[str, "Section"] = field(default_factory=dict)


class ScriptParser:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    def skip(self) -> None:
        while self.pos < len(self.text):
            match = re.match(r"\s+|//[^\n]*(?:\n|$)|/\*.*?\*/",
                             self.text[self.pos:], re.DOTALL)
            if match is None:
                break
            self.pos += match.end()

    def parse(self, nested: bool = False, depth: int = 0) -> Section:
        if depth > 64:
            raise ValueError("Setup script nesting exceeds 64 sections")
        result = Section()
        while True:
            self.skip()
            if self.pos == len(self.text):
                if nested:
                    raise ValueError("Unclosed setup section")
                return result
            char = self.text[self.pos]
            if char == "}" and nested:
                self.pos += 1
                return result
            if char == "[":
                end = self.text.find("]", self.pos)
                if end < 0:
                    raise ValueError("Unclosed section name")
                name = self.text[self.pos + 1:end].strip().lower()
                self.pos = end + 1
                self.skip()
                if not name or self.text[self.pos:self.pos + 1] != "{":
                    raise ValueError("Missing section name or opening brace")
                self.pos += 1
                if name in result.sections:
                    raise ValueError("Duplicate section: " + name)
                result.sections[name] = self.parse(True, depth + 1)
            else:
                match = re.match(r"([^{}\[\]=;\s]+)\s*=", self.text[self.pos:])
                if match is None:
                    raise ValueError("Invalid setup syntax at offset " + str(self.pos))
                name = match.group(1).lower()
                self.pos += match.end()
                end = self.text.find(";", self.pos)
                if end < 0:
                    raise ValueError("Unterminated setup value: " + name)
                value = self.text[self.pos:end].strip()
                if len(value) >= 2 and value[0] == value[-1] == '"':
                    value = value[1:-1]
                if name in result.values:
                    raise ValueError("Duplicate setup value: " + name)
                result.values[name] = value
                self.pos = end + 1


def read_exact(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("Truncated replay header or setup script")
    return data


def read_replay(path: Path) -> tuple[datetime, str, list[str]]:
    with gzip.open(path, "rb") as stream:
        magic, version, header_size, _, game_id, timestamp, script_size = (
            HEADER.unpack(read_exact(stream, HEADER.size))
        )
        if magic != b"spring demofile\0" or version != 5:
            raise ValueError("Unsupported replay magic or format version")
        if not 352 <= header_size <= MAX_HEADER:
            raise ValueError("Invalid replay header size")
        if not 0 < script_size <= MAX_SCRIPT:
            raise ValueError("Invalid replay setup script size")
        read_exact(stream, header_size - HEADER.size)
        text = read_exact(stream, script_size).decode("utf-8").rstrip("\0")
    root = ScriptParser(text).parse()
    game = root.sections.get("game")
    if game is None:
        raise ValueError("Missing GAME section")
    players = []
    for name, section in game.sections.items():
        if not re.fullmatch(r"player\d+", name):
            continue
        player = section.values.get("name")
        spectator = section.values.get("spectator")
        if not player or spectator not in ("0", "1"):
            raise ValueError("Missing/invalid player name or spectator flag: " + name)
        if spectator == "0":
            players.append(player)
    return datetime.fromtimestamp(timestamp, timezone.utc), game_id.hex(), players


def filename_time(name: str) -> datetime | None:
    match = FILENAME_TIME.match(name)
    if match is None:
        return None
    value = match.group(1)
    if "-" not in value:
        fmt = "%Y%m%d_%H%M%S"
    else:
        fmt = "%Y-%m-%d_%H-%M-%S-%f" if len(value) > 19 else "%Y-%m-%d_%H-%M-%S"
    try:
        return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
    except ValueError:
        # Unrecognised timestamps must be checked against the embedded header.
        return None


def utc_time(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamps must include an explicit UTC offset")
    return result.astimezone(timezone.utc)


def scan(root: Path, start: datetime, end: datetime, attendees: set[str]) -> dict:
    if not root.is_dir():
        raise ValueError("Replay root is not a directory: " + str(root))
    manifest = {
        "root": str(root.resolve()),
        "start_utc": start.isoformat(),
        "end_utc_exclusive": end.isoformat(),
        "password_filter": False,
        "files_seen": 0,
        "files_parsed": 0,
        "matches": [],
        "errors": [],
    }

    def walk_error(error: OSError) -> None:
        manifest["errors"].append({"path": error.filename, "error": str(error)})

    for directory, dirs, files in os.walk(root, onerror=walk_error):
        dirs.sort()
        for name in sorted(files):
            if not name.endswith(".sdfz"):
                continue
            path = Path(directory) / name
            manifest["files_seen"] += 1
            named_start = filename_time(name)
            if named_start is not None and not start <= named_start < end:
                continue
            try:
                if path.is_symlink():
                    raise ValueError("Refusing replay symlink")
                before = path.stat()
                manifest["files_parsed"] += 1
                started, game_id, players = read_replay(path)
                matched = sorted(attendees.intersection(players))
                if not start <= started < end or not matched:
                    continue
                digest = hashlib.sha256()
                with path.open("rb") as replay:
                    for chunk in iter(lambda: replay.read(1024 * 1024), b""):
                        digest.update(chunk)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError("Replay changed during scanning; retry after game ends")
                manifest["matches"].append({
                    "path": str(path.resolve()),
                    "game_id": game_id,
                    "start_utc": started.isoformat(),
                    "matching_players": matched,
                    "size": after.st_size,
                    "sha256": digest.hexdigest(),
                })
            except (OSError, EOFError, ValueError, OverflowError, zlib.error) as error:
                manifest["errors"].append({"path": str(path), "error": str(error)})
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--attendees", type=Path, required=True)
    parser.add_argument("--start", required=True, help="Inclusive ISO timestamp with offset")
    parser.add_argument("--end", required=True, help="Exclusive ISO timestamp with offset")
    args = parser.parse_args()
    try:
        start, end = utc_time(args.start), utc_time(args.end)
        if start >= end:
            raise ValueError("Start must precede end")
        attendees = {line.strip() for line in args.attendees.read_text(
            encoding="utf-8-sig").splitlines() if line.strip()}
        if not attendees:
            raise ValueError("Attendee list is empty")
        manifest = scan(args.root, start, end, attendees)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(manifest, indent=2))
    # Per-file errors remain structured so Ansible can persist them before failing.
    return 0


if __name__ == "__main__":
    sys.exit(main())

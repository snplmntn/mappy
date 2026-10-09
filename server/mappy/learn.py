"""What shoppers picked when a brand was missing, so the next shopper sees that store first.
Counts only (brand -> place id -> picks); no phone identity. Saved as JSON on the edge laptop."""

import json
from pathlib import Path

from .brands import _norm


class Picks:
    def __init__(self, path: Path | None):
        self.path = path
        self.counts: dict[str, dict[str, int]] = {}
        if path is not None and path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):  # anything else is someone else's file: start empty
                    self.counts = {k: {p: n for p, n in v.items() if isinstance(n, int)}
                                   for k, v in data.items() if isinstance(v, dict)}
            except (OSError, ValueError):
                pass

    def record(self, asked: str, place_id: str) -> None:
        picks = self.counts.setdefault(_norm(asked), {})
        picks[place_id] = picks.get(place_id, 0) + 1
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps(self.counts), encoding="utf-8")
            tmp.replace(self.path)

    def ranked(self, asked: str) -> list[str]:
        """Place ids by pick count, most first; ties keep the order they were first picked."""
        picks = self.counts.get(_norm(asked), {})
        return sorted(picks, key=lambda pid: -picks[pid])

    def top(self, asked: str) -> str | None:
        return next(iter(self.ranked(asked)), None)

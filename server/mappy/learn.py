"""What shoppers picked when a brand was missing, so the next shopper sees that store first.
Counts only (brand -> place id -> picks); no phone identity. Saved as JSON on the edge laptop."""

import json
import logging
import threading
from pathlib import Path

from .brands import _norm

log = logging.getLogger("mappy")


class Picks:
    def __init__(self, path: Path | None):
        self.path = path
        self.counts: dict[str, dict[str, int]] = {}
        self._lock = threading.Lock()  # /api/pick is a sync route: concurrent taps share this object
        if path is not None and path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):  # anything else is someone else's file: start empty
                    self.counts = {k: {p: n for p, n in v.items() if isinstance(n, int)}
                                   for k, v in data.items() if isinstance(v, dict)}
            except (OSError, ValueError):
                pass

    def record(self, asked: str, place_id: str) -> None:
        with self._lock:
            picks = self.counts.setdefault(_norm(asked), {})
            picks[place_id] = picks.get(place_id, 0) + 1
            self._save()

    def _save(self) -> None:
        """Best effort: a pick that could not be written is still counted for this run."""
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps(self.counts), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as e:
            log.warning("could not save picks to %s: %s", self.path, e)

    def ranked(self, asked: str) -> list[str]:
        """Place ids by pick count, most first; ties keep the order they were first picked."""
        picks = self.counts.get(_norm(asked), {})
        return sorted(picks, key=lambda pid: -picks[pid])

    def top(self, asked: str) -> str | None:
        return next(iter(self.ranked(asked)), None)

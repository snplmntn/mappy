"""Live view of the edge box for the projector: which phone asked what, which engine answered, how fast,
and whether this laptop can reach the internet at all. In memory only; nothing is written to disk."""

import asyncio
import ctypes
import platform
import statistics
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass

ENGINES = ("rules", "llm", "cache", "fallback")
ACTIVE_S = 15 * 60
CHECK_EVERY_S = 10
PROBE = ("1.1.1.1", 53)
LOCAL_HOSTS = ("127.0.0.1", "::1", "testclient")


@dataclass
class EdgeEvent:
    at: float
    phone: str
    message: str
    engine: str
    intent: str
    ms: int


class EdgeMonitor:
    def __init__(self, max_events: int = 60):
        self.events: deque[EdgeEvent] = deque(maxlen=max_events)
        self.served = dict.fromkeys(ENGINES, 0)
        self.llm_ms: deque[int] = deque(maxlen=100)
        self._phones: dict[str, int] = {}
        self._last_seen: dict[str, float] = {}

    def phone(self, host: str | None) -> str:
        """A stable, friendly name per device: "Phone 1", "Phone 2", ... in the order they first connect."""
        host = host or "?"
        if host in LOCAL_HOSTS:
            return "Laptop"
        if host not in self._phones:
            self._phones[host] = len(self._phones) + 1
        return f"Phone {self._phones[host]}"

    def seen(self, host: str | None, now: float | None = None) -> None:
        self._last_seen[self.phone(host)] = time.time() if now is None else now

    def record(self, host: str | None, message: str, engine: str, intent: str, ms: int,
               now: float | None = None) -> None:
        now = time.time() if now is None else now
        self.seen(host, now)
        engine = engine if engine in ENGINES else "fallback"
        self.served[engine] += 1
        if engine == "llm":
            self.llm_ms.append(ms)
        self.events.appendleft(EdgeEvent(now, self.phone(host), message[:120], engine, intent, ms))

    def stats(self, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        total = sum(self.served.values())
        return {
            "phones": sum(1 for t in self._last_seen.values() if now - t <= ACTIVE_S),
            "requests": total,
            "served": self.served,
            "without_llm_pct": round(100 * (total - self.served["llm"]) / total) if total else None,
            "llm_median_ms": round(statistics.median(self.llm_ms)) if self.llm_ms else None,
            "events": [asdict(e) for e in self.events],
        }


async def internet_reachable(timeout_s: float = 1.5) -> bool:
    """True if a public DNS server answers a TCP connect. Mappy itself never calls out; this only proves it."""
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(*PROBE), timeout_s)
        writer.close()
        return True
    except (OSError, asyncio.TimeoutError):
        return False


class _MemoryStatus(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def cpu_name() -> str:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return " ".join(str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).split())
        except OSError:
            pass
    return platform.processor() or platform.machine()


def memory() -> dict | None:
    """Total RAM and percent in use. Windows only (the demo laptop); None elsewhere."""
    if sys.platform != "win32":
        return None
    m = _MemoryStatus(dwLength=ctypes.sizeof(_MemoryStatus))
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        return None
    return {"total_gb": round(m.ullTotalPhys / 2**30, 1), "used_pct": int(m.dwMemoryLoad)}


class CpuMeter:
    """Whole-machine CPU use since the previous reading, from GetSystemTimes. Windows only."""

    def __init__(self):
        self._prev: tuple[int, int] | None = None

    def read(self) -> int | None:
        if sys.platform != "win32":
            return None
        idle, kernel, user = (ctypes.c_ulonglong() for _ in range(3))
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        busy_total = (kernel.value + user.value - idle.value, kernel.value + user.value)
        prev, self._prev = self._prev, busy_total
        if prev is None or busy_total[1] == prev[1]:
            return None
        return round(100 * (busy_total[0] - prev[0]) / (busy_total[1] - prev[1]))


class Probe:
    """Runs a slow async check at most every `every_s` seconds and serves the cached answer in between."""

    def __init__(self, check, every_s: float = CHECK_EVERY_S):
        self._check = check
        self._every_s = every_s
        self._at = float("-inf")
        self._value = None

    async def get(self):
        if time.monotonic() - self._at >= self._every_s:
            self._at = time.monotonic()
            self._value = await self._check()
        return self._value

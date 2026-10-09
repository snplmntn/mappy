"""Measure message understanding on the Taglish eval set.

Usage: python tools/eval.py [--mall PATH] [--llm-only] [--threads 4] [--out docs/eval-results.md]
Reports only measured numbers; the pitch quotes these and nothing else.
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from mappy.embed import E5Embedder, HashEmbedder  # noqa: E402
from mappy.llm import LLMBusy, LLMClient, LLMError, fallback_extract, trip_summary  # noqa: E402
from mappy.mall import load_mall  # noqa: E402
from mappy.models import Errand, Trip  # noqa: E402
from mappy.rules import parse  # noqa: E402
from mappy.search import Search  # noqa: E402

STD_TRIP = Trip(errands=[
    Errand(id="e1", label="Phone repair", query="phone repair", category="phone_repair",
           candidates=[], duration_min=45, **{"async": True}),
    Errand(id="e2", label="Kain", query="kain", category="food", candidates=[], duration_min=30),
    Errand(id="e3", label="Damit", query="damit", category="clothing", candidates=[], duration_min=25),
])


def top_category(search: Search, query: str) -> str | None:
    """What the app does with an uncategorized errand: take the best search hit's category."""
    hits = search.search(query, k=1)
    return search.mall.places[hits[0][0]].category if hits else None


def f1(expected: set, got: set) -> float:
    if not expected and not got:
        return 1.0
    tp = len(expected & got)
    if tp == 0:
        return 0.0
    p, r = tp / len(got), tp / len(expected)
    return 2 * p * r / (p + r)


async def run(args) -> str:
    mall = load_mall(args.mall)
    e5 = ROOT / "models" / "e5"
    search = Search(mall, E5Embedder(e5) if e5.exists() else HashEmbedder())
    categories = sorted(mall.category_defaults)
    llm = LLMClient(args.base_url, categories, model=args.model, threads=args.threads, timeout_s=60)
    rows, lat_all, lat_llm = [], [], []
    stats = {"intent": 0, "cat_f1": [], "ops": [], "lm": [], "rules": 0, "fallback": 0}
    lines = [line for line in (ROOT / "server" / "eval" / "taglish.jsonl").read_text(encoding="utf-8").splitlines() if line]
    for line in lines:
        case = json.loads(line)
        trip = STD_TRIP if case["trip"] == "std" else Trip()
        exp = case["expect"]
        t0 = time.perf_counter()
        x = None if args.llm_only else parse(case["msg"], trip, search)
        if x is None:
            try:
                x = await llm.extract(case["msg"], trip, trip_summary(trip, lambda p: p))
                lat_llm.append(time.perf_counter() - t0)
            except (LLMBusy, LLMError, asyncio.TimeoutError):
                x = fallback_extract(case["msg"], trip)
                stats["fallback"] += 1
        else:
            stats["rules"] += 1
        lat_all.append(time.perf_counter() - t0)
        ok_intent = x.intent == exp["intent"]
        stats["intent"] += ok_intent
        detail = []
        if "categories" in exp:
            got = {e.category or top_category(search, e.query) for e in x.errands} - {None}
            score = f1(set(exp["categories"]), got)
            stats["cat_f1"].append(score)
            detail.append(f"cats {sorted(got)} f1={score:.2f}")
        if "ops" in exp:
            got_ops = {e.op for e in x.edits}
            ok = got_ops == set(exp["ops"])
            stats["ops"].append(ok)
            detail.append(f"ops {sorted(got_ops)} {'ok' if ok else 'MISS'}")
        if "landmarks" in exp:
            got_lm = {lm.lower() for lm in x.landmarks}
            ok = {lm.lower() for lm in exp["landmarks"]} <= got_lm
            stats["lm"].append(ok)
            detail.append(f"landmarks {sorted(got_lm)} {'ok' if ok else 'MISS'}")
        rows.append(f"| {'✓' if ok_intent else '✗'} | {x.source} | {case['msg']} | {x.intent} | {'; '.join(detail)} |")
    n = len(lines)

    def pct(v):
        return f"{100 * sum(v) / len(v):.0f}% ({sum(v)}/{len(v)})" if v else "n/a"

    def ms(v):
        if not v:
            return "n/a"
        s = sorted(v)
        return f"median {1000 * statistics.median(s):.0f} ms, p95 {1000 * s[int(0.95 * (len(s) - 1))]:.0f} ms"

    summary = [
        f"# Eval results ({time.strftime('%Y-%m-%d %H:%M')})",
        "",
        f"- Model: `{args.model}` via Ollama, `num_thread={args.threads}`, CPU only. Mall: `{Path(args.mall).name}`."
        f" Mode: {'LLM only' if args.llm_only else 'rules first, then LLM'}.",
        f"- Messages: {n}. Handled by rules: {stats['rules']}. LLM fallbacks: {stats['fallback']}.",
        f"- Intent accuracy: {100 * stats['intent'] / n:.0f}% ({stats['intent']}/{n})",
        f"- Category F1 (find/plan): {statistics.mean(stats['cat_f1']):.2f}" if stats["cat_f1"] else "- Category F1: n/a",
        f"- Edit ops exact: {pct(stats['ops'])}",
        f"- Landmarks found: {pct(stats['lm'])}",
        f"- Latency all messages: {ms(lat_all)}",
        f"- Latency LLM calls: {ms(lat_llm)}",
        "",
        "| ok | source | message | intent | detail |",
        "|---|---|---|---|---|",
    ]
    return "\n".join(summary + rows) + "\n"


def main():
    ap = argparse.ArgumentParser()
    default_mall = ROOT / "data" / "sm-makati" / "mall.json"
    ap.add_argument("--mall", default=str(default_mall if default_mall.exists() else ROOT / "data" / "sample" / "mall.json"))
    ap.add_argument("--base-url", default="http://127.0.0.1:11434")
    ap.add_argument("--model", default="qwen3:1.7b")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--llm-only", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()
    report = asyncio.run(run(args))
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    print("\n".join(report.splitlines()[:11]))


if __name__ == "__main__":
    main()

# How to pitch Mappy

**One line:** Mappy is an offline mall trip planner. Scan a QR code, say what you need, and it plans your whole trip around the waiting. It all runs on one laptop inside the mall, with no internet.

**Tagline:** Lost no more, smiles on every floor.

**Team:** CoolPals · AppBuildersPH Hackathon 2026 · theme: Local AI

---

## The story (same order as the teaser)

Tell it in this order. Each beat matches a scene in the video, so the pitch and the video back each other up.

| # | Beat | Say | Show |
|---|---|---|---|
| 1 | Hook | "Are you lost in the mall too?" Then pause. Let it land. | Teaser opening, or just ask the room |
| 2 | Problem: no signal | "You try maps, but there's no internet. Malls are dead zones: indoors, underground, crowded." | Phone with no signal |
| 3 | Problem: the kiosk | "So you line up at the big directory screen, then forget the way two turns later." | — |
| 4 | Meet Mappy | "Mappy puts the kiosk in every phone, and it plans your whole trip." | Mappy home screen |
| 5 | How you open it | "Scan the QR code in the mall. It opens in your browser. No app to install." | `/print` QR cards |
| 6 | Ask by purpose | "You don't need to know the store. Say what you need." | Type **"My phone screen is cracked"** → phone repair stalls |
| 7 | **The win: smart order** | "Give it your errands. Mappy picks the smartest order: phone to repair first, so you eat and shop while it's being fixed. Nobody told it the order." | Type the errand list → plan card |
| 8 | Walk you there | "Then it walks you there, floor by floor, with elevator-only routes if you have a stroller." | Start navigation → transfer card |
| 9 | The funny one | "And when nature calls? It finds the nearest restroom, fast." | **Nearest restroom** |
| 10 | Local AI | "No internet, no app, no cloud. One laptop in the mall runs it all, and nothing leaves the building." | `/edge` panel |
| 11 | Close | "Lost in the mall? Not anymore. Mappy: lost no more, smiles on every floor." | End card |

**Spend most of the time on beat 7.** It's what makes Mappy different from a map: an errand isn't a point, it's a task with a duration, and Mappy plans around the wait.

---

## 60-second spoken version

> Are you lost in the mall too? *(pause)*
>
> You try maps, but there's no signal indoors. The big directory screen has a line, and you forget the way two turns later.
>
> Meet Mappy. Scan a QR code in the mall and it opens in your browser, with no app to install. You don't need store names: say "my phone screen is cracked" and it finds the repair stalls.
>
> Give it your whole list, in English or Taglish, and it picks the smartest order. Your phone goes to repair first, so you eat and shop while it's fixed. We never told it that order. Then it walks you there floor by floor, and yes, it finds the nearest restroom fast.
>
> And it's all local AI: one laptop inside the mall runs everything. No internet, no cloud, nothing leaves the building.
>
> Lost in the mall? Not anymore.

---

## Live demo script

Use these exact inputs. They're the ones in the teaser and they're known to work.

**Before going on stage**
1. Start the hotspot (`mappy`, mobile data **off**), then run `tools\run.ps1` on the demo laptop.
2. Open `http://localhost:8000/edge` on the laptop, next to the mirrored phone (`scrcpy`).
3. **Warm up the LLM:** send one message that needs it, e.g. *"the guy said it will take two hours"*. The first LLM call takes ~7 s; warm calls take ~0.3 s.
4. On the phone: airplane mode on, Wi-Fi on, scan the Wi-Fi QR, then the app QR from `/print`.
5. **Set the location to "Ground Floor, main entrance"** (scan that location card or tap the chip). Without a location, "Nearest restroom" lists a 3-min restroom above a 1-min one.

**On stage**

| Step | Do | Expect |
|---|---|---|
| 1 | Show `/print` | "Scan. Connect. You're on your way." Wi-Fi QR, app QR, 8 location codes |
| 2 | Type `My phone screen is cracked` | ScreenDoc, FixHub Mobile, QuickFix Gadget Clinic: phone repair, 2nd Floor (all tagged **demo**) |
| 3 | Type `Fix my cracked phone screen, grab lunch, then buy a gift for my mom` | Plan: drop off phone → eat → gift → pick up, with "done by" time and walking minutes |
| 4 | Tap **Start navigation** | Transfer card like "Take Escalator A up to 2nd Floor", floor strip |
| 5 | Back in chat, flip **Elevators only** | Route switches to the elevator |
| 6 | Type `Nearest restroom` | Top result: Ground Floor · 1 min walk |
| 7 | Point at `/edge` | Each request: engine used (rules / cache / local LLM / fallback), latency, CPU, RAM, and **no internet** |

**Optional extras if there's time**
- Re-plan by talking: *"The technician said 1 hour, and I need to leave by 5"* → a "Changed" list.
- Meet a friend: *"My friend is beside Fuel Burgers, across Gong Cha"* → pins, then route.
- Taglish: *"papaayos ko phone ko, kakain, tapos bibili ng regalo"*.

---

## Numbers you can say

All from the README's own measurements (`tools/eval.py`, 50 Taglish messages, CPU only).

| Claim | Number |
|---|---|
| Median answer time (local LLM) | **0.27 s** (p95 0.33 s) |
| Intent accuracy, rules + LLM | **92%** (vs 82% LLM only) |
| Steering edits applied exactly | **100%** (12/12) |
| Landmarks found | **100%** (8/8) |
| Messages handled by rules alone, no LLM | 28 of 50 |
| Model | Qwen3-1.7B, CPU only, plus multilingual-e5-small embeddings |
| Data sent to the internet at runtime | **0** |
| Tests | 123, pure logic |

Those were measured on a Ryzen 7 limited to 4 threads. The demo laptop (i3, 8 GB) is slower per core, so say "measured on our dev machine" if asked.

---

## Why it wins on the theme (Local AI)

- **Malls are connectivity dead zones.** It has to work offline, so local is the only option.
- **One laptop replaces the kiosk** and serves every phone nearby. Each extra question costs nothing.
- **Private by design.** "Pharmacy for X" or "meeting someone" never reaches a cloud.
- **The LLM only extracts structure** (intents, errands, edits). Planning and routing are deterministic, tested code, so answers are reliable.
- **It never hangs.** Rules answer first, with an 8-second timeout and a deterministic fallback after the model.

---

## Likely questions

**"Isn't this just Google Maps indoors?"**
No. Maps needs signal and finds points. Mappy works with zero internet and plans *tasks with durations*: it puts the repair first because that's where the waiting is.

**"Why not use a cloud model?"**
There's no signal inside the mall. Local is also faster to re-plan (no round trip) and keeps what people ask private.

**"Is the map real?"**
The building outline and store names are real SM Makati data. The interior layout is our reconstruction, and the app says so on screen. The three phone repair stalls are fictional and tagged "demo". Loading SM's real floor plans is a data swap.

**"How do people get on it?"**
Scan the Wi-Fi QR, then the app QR. It opens in the browser. Nothing to install, and it works in airplane mode.

**"What does it run on?"**
One laptop: an i3 with 8 GB and no GPU at the demo. Qwen3-1.7B through Ollama, on CPU.

---

## Honesty rules

- Keep the **"demo"** tags visible on fictional stalls.
- Only show `/edge` saying "No internet · fully offline" from the real demo laptop, not from a machine that's online.
- Only quote the numbers above, and say where they were measured.
- The "30 minutes saved" idea was cut from the video. Don't claim a specific time saving.

---

## Links

- Teaser video: see the hackathon submission
- Background: [README.md](../README.md), [docs/eval-results.md](eval-results.md)

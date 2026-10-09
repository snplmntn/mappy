# Mappy: Design Spec

**Event:** AppBuildersPH Hackathon 2026, theme *Local AI*
**Submission deadline:** Oct 10, 10:00 AM, one submission, no edits. Internal freeze: **9:00 AM**.
**Demo:** Cyberzone, SM Makati: 5 min live pitch + 3 min Q&A.

---

## 1. Product

SM's directory kiosks have a queue, a single screen, and no idea *why* you came to the mall.
Mappy puts the kiosk in every phone. Users scan a QR code with no install, and a **local AI**
plans the whole trip.

**Pitch line:** *"An errand isn't a point, it's a task with a duration. We plan your mall trip around waiting time, offline."*

### Core features
1. **Ask by purpose, in Taglish.** "sira screen ng phone ko" finds the phone-repair stalls. The local LLM normalizes the request into intents, and local embeddings rank stores by meaning, not by keyword.
2. **Multi-stop trip planning that respects waiting time.** Repair/drop-off services become a DROP stop and a PICK stop. The planner orders stops so the user's own errands fill the wait. The order is **derived** from a cost function, never hardcoded.
3. **Multi-floor routing.** Each floor gets its own leg. Escalators are directional, elevators stop at every floor, and an elevator-only mode is available for accessibility.
4. **Positioning without GPS.**
   - **Location QR (anchor):** scanning a QR at a known spot gives exact position, floor and heading, like a kiosk.
   - **Describe what you see:** landmark matching gives approximate position; the user confirms by tapping a pin.
   - **Tap on map:** manual override.
5. **Meet a friend.** The friend describes what they see, the user types it in, Mappy locates them and routes the user there.
6. **Steer the trip by talking.** New information typed into chat changes the plan:
   - *"sabi ng technician 30 mins lang"* (the technician said only 30 minutes): the repair becomes 30 min.
   - *"ready daw by 4pm"* (they said it'll be ready by 4pm): a fixed ready time.
   - *"gutom na ko, kain muna"* (I'm hungry, let's eat first): food moves to first.
   - *"kailangan ko umalis ng 6"* (I need to leave by 6): a deadline.
   - *"naiwan ko na yung phone"* (I've left my phone with them): marked as dropped off; the clock starts now.
   - *"wag na H&M"* (skip H&M): removed.

   The local LLM turns the message into **edits** to the trip; deterministic code applies them and re-plans. The reply shows exactly what changed and why the order moved.

### Why local (the mandatory submission answer)
- **Malls are connectivity dead zones.** Indoors, below ground, crowded cell towers, captive-portal Wi-Fi. Navigation must work with **zero internet**. The demo runs in airplane mode on a hotspot with no WAN.
- **Edge box replaces the kiosk.** One local machine serves every phone in the building. Nothing leaves the mall, and per-query cost is zero at mall scale.
- **Private intent.** "Pharmacy for X" and "meeting someone" stay inside the building.
- **Latency.** Re-planning on every edit is instant, with no cloud round trip.

### Data honesty
The map is a **reconstruction**: real store names (from public listings) on a layout we drew inside SM Makati's real building footprint (OpenStreetMap). The app shows a small "Layout reconstructed" note. In the pitch: *"With SM's floor plans, this is a data swap."*

---

## 2. Constraints that shaped the design

| Constraint | Consequence |
|---|---|
| Phones join over QR, no install | Web app served by the laptop over plain `http://` on a LAN IP |
| `http://` on a LAN IP is **not a secure context** | **No** mic, camera, service worker, clipboard or Web Share. Text input only. Sharing means showing an on-screen QR. `localStorage` still works. |
| Low-end Android (2–3 GB RAM, Android Go class) | Under 150 KB of gzipped JS, no map library, SVG drawn from data, one floor at a time, system fonts |
| Spare Android phone as access point, mobile data OFF | Up to ~10 clients. **The subnet may change per hotspot session**, so the QR is generated at server start (see §8) |
| Android routes around "no internet" Wi-Fi via mobile data | Users must enable **airplane mode, then Wi-Fi**. The join card says so. It is also the demo's offline proof. |
| One machine serves up to ~10 phones | LLM calls have a 6 s timeout with a deterministic fallback; embeddings are precomputed; the model stays loaded |
| 3 builders, ~16 h | Two frozen contracts: `mall.json` and the HTTP API. No one blocks anyone else. |

---

## 3. Architecture

```
 Android phone (Chrome)               Edge box (laptop)
 +-----------------------+   HTTP   +----------------------------------------+
 | web/  chat + SVG map  | -------> | server/  FastAPI (Python 3.12)         |
 | (static, <150KB gz)   | <------- |  |- mall      load + validate + graph  |
 +-----------------------+   JSON   |  |- router    Dijkstra, all-pairs      |
                                    |  |- search    embeddings + fuzzy       |
                                    |  |- planner   wait-aware ordering      |
                                    |  |- locator   landmark matching        |
                                    |  |- ai        OpenAI-compatible client |
                                    |  '- api       routes, QR, static       |
                                    +-------------------+--------------------+
                                                        | localhost
                                    +-------------------v--------------------+
                                    | LM Studio / llama.cpp (Vulkan, RX 6600) |
                                    |  or Ollama: chat model + embed model    |
                                    +----------------------------------------+
```

The phone runs no AI. The edge box runs all of it. The phone downloads `mall.json` once and draws the map itself.

### Repository layout
```
server/      Python backend (owner: A)
  mappy/     mall.py router.py search.py planner.py trip.py locator.py ai.py api.py
  tests/     unit tests for pure logic only (router, planner, locator, mall validation)
web/         phone app -> builds to web/dist, served by server (owner: B)
editor/      map editor, static HTML (owner: B, used by C)
data/
  sample/mall.json      tiny 2-floor fixture for dev + tests
  sm-makati/mall.json   the demo map (owner: C)
tools/       osm_outline.py (building footprint -> floor outline)
docs/
```

---

## 4. Contract A: `mall.json`

Coordinates are in each floor's own pixel space. `scale_m_per_px` converts to meters. Walking speed is 1.2 m/s.

```json
{
  "mall": { "id": "sm-makati", "name": "SM Makati",
            "note": "Store names from public listings; layout reconstructed." },

  "floors": [
    { "id": "GF", "name": "Ground Floor", "level": 0,
      "width": 1000, "height": 700, "scale_m_per_px": 0.15,
      "outline": [[40,60],[960,60],[960,640],[40,640]] }
  ],

  "nodes": [
    { "id": "GF-c01", "floor": "GF", "x": 120, "y": 340 }
  ],
  "edges": [ ["GF-c01", "GF-c02"] ],

  "connectors": [
    { "id": "esc-a-up",     "kind": "escalator", "direction": "up",   "stops": ["GF-esc-a", "2F-esc-a"] },
    { "id": "esc-a-down",   "kind": "escalator", "direction": "down", "stops": ["2F-esc-a2", "GF-esc-a2"] },
    { "id": "elev-1",       "kind": "elevator",  "direction": "both", "stops": ["LG-el1", "GF-el1", "2F-el1", "3F-el1", "4F-el1"] },
    { "id": "bridge-annex", "kind": "bridge",    "direction": "both", "stops": ["2F-br1", "AX2-br1"] }
  ],

  "places": [
    { "id": "starbucks-gf", "name": "Starbucks", "floor": "GF",
      "rect": [600, 400, 60, 40], "node": "GF-c07",
      "category": "cafe", "tags": ["coffee", "frappuccino", "pastry"] },
    { "id": "cz-fixit-1", "name": "FixIt Mobile", "floor": "4F",
      "rect": [210, 160, 40, 30], "node": "4F-c04",
      "category": "phone_repair", "tags": ["screen replacement", "battery"],
      "service": { "duration_min": 60 } }
  ],

  "category_defaults": {
    "phone_repair": { "duration_min": 45, "async": true },
    "shoe_repair":  { "duration_min": 30, "async": true },
    "food":         { "duration_min": 30, "async": false },
    "cafe":         { "duration_min": 20, "async": false },
    "clothing":     { "duration_min": 25, "async": false },
    "pharmacy":     { "duration_min": 5,  "async": false },
    "atm":          { "duration_min": 3,  "async": false },
    "restroom":     { "duration_min": 5,  "async": false }
  },

  "anchors": [
    { "id": "gf-mrt-entrance", "label": "GF - MRT/Bridge Entrance",
      "floor": "GF", "node": "GF-c01", "heading_deg": 90 }
  ]
}
```

**Rules (validated at load; the server refuses to start on violation):**
- Every `node`, `edges` endpoint, connector stop and place `node` refers to an existing node.
- Each connector stop is on a different floor, and stops are listed in travel order.
- `places[].service` overrides `category_defaults[category]`, and every category has a default.
- Store adjacency is **derived** (same floor, door-to-door distance under 15 m). It is never authored.
- Restrooms (CR), ATMs and connectors are places/connectors too, drawn as icons on every floor.

**Connector costs (seconds):** escalator 30 per floor; elevator 60 wait + 10 per floor; bridge = walking distance. `elevator_only` removes escalator edges.

---

## 5. Contract B: HTTP API

All JSON. Base path `/api`. Static `web/dist` is served at `/`.

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/mall` | - | `mall.json` (with ETag; the phone caches it in memory) |
| POST | `/api/chat` | `{ message, at?, now, trip? }` | `{ reply, result, trip }` (see below) |
| POST | `/api/plan` | `{ from, now, trip }` | `Plan` |
| POST | `/api/locate` | `{ text, floor? }` | `{ candidates[], ask? }` |
| GET | `/api/health` | - | `{ ok, model, embed_model, llm_ok }` |
| GET | `/print` | - | Printable page: Wi-Fi QR + app QR + all anchor QRs, built from the **current** server IP |

**`/api/chat` result** is one of these:
- `{ type: "places", query, places: [PlaceRef] }`: "where can I fix my phone?"
- `{ type: "plan", plan: Plan, changes: string[] }`: several errands, or a steering message applied to the current trip. `changes` lists human-readable edits, e.g. "Phone repair: 45 -> 30 min (you said)".
- `{ type: "locate", candidates: [Candidate], ask? }`: "I'm beside Jollibee, facing H&M" / a friend's description
- `{ type: "text" }`: small talk or a clarification; `reply` holds the text

`reply` is a short **templated** sentence (Taglish-friendly). The LLM never writes free prose, so nothing needs streaming.

**The trip lives on the phone.** The server is stateless. The phone sends `trip` with every call and replaces it with the `trip` returned from `/chat`, so several phones never share state and no session store is needed. `now` is the phone's clock as `"HH:MM"`.

```ts
type At = { anchor: string } | { node: string }
type Errand = {
  id: string,                      // "e1", stable for the whole trip
  label: string,                   // "Phone screen repair"
  query: string, candidates: string[] /* place ids */, chosen?: string,
  duration_min: number, duration_source: "default" | "store" | "user",
  async: boolean, ready_at?: string /* "HH:MM" */,
  status: "todo" | "dropped" | "done", dropped_at?: string
}
type OrderRule = { errand: string, rule: "first" | "last" | "before" | "after", other?: string }
type Trip = {
  errands: Errand[],
  constraints: { deadline?: string, order: OrderRule[], elevator_only?: boolean }
}
type Plan = {
  stops: { kind: "visit"|"drop"|"pick", place: string, arrive_min: number, leave_min: number, reason: string }[],
  legs:  { floor: string, path: [number, number][], instruction: string,
           connector?: { id: string, kind: string, to_floor: string } }[],
  total_min: number, walk_min: number, idle_min: number,
  finish_at: string, warnings: string[]   // e.g. "Won't finish by 6:00. Skip Clothing?"
}
type Candidate = { node: string, floor: string, x: number, y: number, score: number, matched: string[] }
```

`web/mock-api/*.json` holds one canned response per endpoint, so B can build without the server.

---

## 6. Server components

### 6.1 `ai`: local models
- One OpenAI-compatible client (`LLM_BASE_URL`, `LLM_MODEL`, `EMBED_MODEL`), so LM Studio, llama.cpp-server and Ollama are interchangeable.
- **Chat model:** qwen2.5-3b-instruct (Q4) by default. Try 7B on the RX 6600 XT. Pick in the smoke test using 10 Taglish prompts.
- **Embedding model:** bge-m3 (multilingual, so the Taglish fallback still works). Place vectors are precomputed at startup and cached to disk, keyed by the hash of `mall.json`.
- **One extraction call per message**, with a JSON-schema-constrained output. When a trip exists, the prompt includes a compact list of its errands (`e1: Phone screen repair, FixIt Mobile 4F, 45 min, async, todo`) so the model can refer to them by id:
  ```json
  { "intent": "find|plan|edit|locate|other",
    "errands":   [{ "query_en": "phone screen repair", "category_hint": "phone_repair" }],
    "edits": [
      { "op": "set_duration", "errand": "e1", "minutes": 30 },
      { "op": "set_ready_at", "errand": "e1", "time": "16:00" },
      { "op": "add",          "query_en": "gift for mom" },
      { "op": "remove",       "errand": "e3" },
      { "op": "order",        "errand": "e2", "rule": "first" },
      { "op": "deadline",     "time": "18:00" },
      { "op": "status",       "errand": "e1", "status": "dropped" },
      { "op": "choose",       "errand": "e2", "place_hint": "the one on 3F" },
      { "op": "elevator_only","value": true }
    ],
    "landmarks": [ "Jollibee", "H&M" ],
    "floor_hint": "4F" }
  ```
- **Timeout 6 s, then fallback:** split the message on `, / and / at / tapos / then / saka`, embed each chunk, and set intent to `plan` if there are 2 or more chunks, else `find`. For steering, the fallback catches durations with a regex (`30 min`, `1 oras`, `1 hr`) and applies them to the only async errand. If there are several, it asks which. The demo never hangs.

### 6.1b `trip`: applying edits (pure, unit-tested)
`apply_edits(trip, edits, now) -> (trip, changes[], question?)`. Deterministic, never calls a model.
- It validates every errand id. An unknown or ambiguous reference returns a `question` ("Which one: phone repair or shoe repair?") instead of guessing.
- `status: dropped` sets `dropped_at = now`. `status: done` removes the errand from planning but keeps it in the trip so the UI can show a checkmark.
- `set_duration` sets `duration_source = "user"`, and the stop's reason then says so: "Drop off first: repair takes 30 min (sabi ng technician)."
- `order` rules that contradict each other: the newest one wins, and a change line says so.
- Every applied edit produces one human-readable `changes[]` line, shown on the plan card.

### 6.2 `search`
Score = 0.7 x cosine(query, place text) + 0.3 x fuzzy name match, plus a bonus when `category_hint` matches. Place text is `name + category + tags`. Return the top-k above a threshold. Restrooms, ATMs and similar quick-chip queries map to a category directly and skip the LLM.

### 6.3 `router`
- Dijkstra over a graph built from nodes, edges and connectors (directional escalators).
- **All-pairs table between place nodes and anchors**, computed at startup (~200 sources), so the planner only does lookups. One table per mode (normal / elevator-only).
- Path to legs: split the path at connector edges; each leg = one floor polyline + instruction.

### 6.4 `planner`: the differentiator
1. Errands -> stops. A sync errand becomes one `visit` (dwell = duration). An async errand becomes `drop` (dwell 3) + `pick` (dwell 3) with `ready = drop_leave + duration`.
2. Enumerate stop orders (with `drop` before `pick`) x one candidate place per errand (top 3).
3. Simulate the clock from `from`: walk via the table, dwell, and **idle if arriving at `pick` before `ready`**.
4. Cost = `total_min + 0.5*idle_min + soft_order_penalty`. The soft penalty is a small table, never dominant: e.g. clothing before food +3 ("shop after eating"), restroom last +2.
5. Return the cheapest plan, with a human `reason` for each stop: "Drop off first: repair takes 45 min", "Eat while waiting", "Pick up: ready by 3:45".
6. Cap: at most 5 errands. Above about 40k combinations, fall back to greedy nearest-feasible.
7. **Steering constraints:**
   - The clock starts at `now`.
   - `ready_at` overrides `drop_leave + duration`.
   - A `dropped` errand contributes only its `pick` stop, ready at `dropped_at + duration` (or `ready_at`).
   - `done` errands are skipped.
   - `order` rules are **hard filters** on permutations.
   - `chosen` fixes the candidate place.
   - A deadline is soft: it adds +100 per minute late, and a `warnings` entry suggests what to drop.

**Acceptance example (unit test):** errands = phone repair (45, async), food (30), clothing (25), each with one candidate. Expected order: drop repair -> food -> clothing -> pick repair, with idle ~ 0 when walking is short. No hardcoded rule produces this. Second case, using the same test map with the repair stall placed on a different floor from food and clothing: at 5 min the plan must pick up before leaving the repair floor (drop -> pick -> food -> clothing), because walking back costs more than the short wait.

### 6.5 `locator`
1. Resolve each landmark to **all** matching place instances (search, name-weighted).
2. Candidate nodes = corridor nodes on floors with at least one match (filtered by `floor_hint` if given).
3. Score(node) = sum over landmarks of the distance to that landmark's nearest instance. Add +40 m when an instance is more than 25 m away ("not visible").
4. Return the top 3 after merging nodes within 8 m. Set `ask` to `"floor"` if the top candidates are on different floors, or `"more_landmarks"` if the top two scores are within 15%.
5. Orientation-free by design. Directions after a landmark fix use landmarks ("walk toward H&M"). Left and right appear only after an anchor scan, when heading is known.

---

## 7. Phone UI (owner: B)

Chat first, map as result. Matches the kiosk look.

- **Top bar:** current position "GF - MRT Entrance" (tap to change: scan, describe, or pick on map) + "Offline - Local AI" badge.
- **Quick chips above the input:** *Kain, CR, ATM, Phone repair, Pharmacy, Find friend*.
- **Chat result cards:**
  - *Places:* a ranked list, each with floor badge + walking minutes; tapping a place routes there.
  - *Plan:* numbered timeline with times and `reason` lines; remove or swap a stop and it re-plans; "Start" opens the map.
  - *Plan after steering:* a "What changed" list (`changes[]`) at the top, stops that moved highlighted, and `warnings` shown as an amber banner.
  - Each stop's duration is tappable (15/30/45/60/90 chips). A tap sends the same `set_duration` edit through `/api/plan`, so typing and tapping behave identically.
  - During the trip, each stop has a **Done** / **Dropped off** button that sends a `status` edit.
  - *Locate:* 1-3 pins on a mini map, "Is this you?" buttons, and the floor question if `ask = "floor"`.
- **Map screen:**
  - SVG drawn from `mall.json`: floor outline, store rectangles + labels, icons for escalators, elevators and CRs.
  - Only the route for the current floor's leg is drawn, with numbered stop pins.
  - **Step header:** "Step 2 of 4 - 4F Cyberzone". **Transfer card:** "Take Escalator A up to 2F", then Next, which switches floor automatically.
  - **Floor strip** on the side (LG GF 2F 3F 4F AX): floors on the route highlighted, current one filled, any floor tappable.
  - Pan/zoom via CSS transform + pointer events. No library.
- **Settings:** elevator-only toggle.
- **Share my spot:** an on-screen QR of `/?at=node:<id>`.
- **Budget:** under 150 KB of gzipped JS; tested on the team's cheapest Android with Chrome DevTools at 6x CPU throttle. Framework is B's choice (Preact/vanilla recommended) as long as it builds to static files against the frozen API.
- **Entry:** `/?at=<anchor_id>` sets position immediately (location QR). Plain `/` asks for a location.

---

## 8. Network and demo setup

1. Spare Android phone: hotspot SSID `mappy`, WPA2, **mobile data off**. The laptop joins it.
2. Laptop: firewall inbound rule for the server port on **all profiles**; sleep disabled; model preloaded (keep-alive).
3. The server binds `0.0.0.0:8000`, detects its LAN IP at startup, and prints the app URL + QR in the terminal. `/print` renders the Wi-Fi QR (`WIFI:S:mappy;T:WPA;P:<pw>;;`), the app QR and the anchor QRs with the **current** IP.
4. **Smoke test tonight:** check whether the hotspot subnet stays the same across hotspot restarts. If it does, print the anchor cards. If not, show the anchor QRs on a screen (laptop or second phone) instead of on paper.
5. Judge flow: scan the Wi-Fi QR -> airplane mode + Wi-Fi on -> scan the app QR or an anchor card.
6. Projector: one phone mirrored via **scrcpy over USB**.

### Demo script (5 min)
1. Problem (30 s): the kiosk queue; no signal in malls.
2. Show the Wi-Fi panel: **no internet**. Judges scan the anchor card "4F - Cyberzone entrance".
3. Type: *"papaayos ko screen ng phone ko, kakain, tapos bibili ng regalo kay mama"* (I'll get my phone screen fixed, eat, then buy a gift for Mom). The plan appears: drop -> eat -> shop -> pick. Line: **"we never told it that order."**
4. Steer it in chat: *"sabi ng technician 1 oras daw, tapos kailangan ko umalis ng 5"* (the technician said 1 hour, and I need to leave by 5). The repair becomes 60 min and the deadline is set; the plan re-orders and shows a "What changed" list. If it no longer fits, a warning suggests what to drop.
5. Multi-floor step-through with the transfer card; toggle elevator-only.
6. Meet a friend: *"nasa tabi ako ng Starbucks, katapat ng H&M"* (I'm next to Starbucks, across from H&M) -> pin -> route.
7. Close: why local, and the data swap to SM's real plans.

---

## 9. Team split and timeline (from about 5 PM Oct 9)

| | **A: Sean (engine + AI + server)** | **B: UI/UX** | **C: data + submission** |
|---|---|---|---|
| 5:00-6:00 | Smoke test (hotspot, firewall, model on GPU), scaffold, `data/sample/mall.json` | Read contracts, set up `web/`, mock API | Store list CSV from public listings: name, floor, category |
| 6:00-9:00 | mall loader + validation, router, planner + unit tests | **Map editor** (outline, nodes, edges, connectors, place rects, anchors; exports `mall.json`) | Category/service table; floor plan of zones (section 10) |
| 9:00-12:00 | ai extraction + fallback, trip edits, search, `/chat` orchestration | Phone UI: chat, cards, map, floor strip | Lay out all floors in the editor |
| 12:00-2:00 | locator, `/print`, integrate the real map | Map steps + transfer cards; cheap-phone perf pass | Anchors; fix data issues found by validation |
| 2:00-3:00 | End-to-end on the hotspot, the **unplug test**, bug fixes | Polish | Rehearse the demo script |
| 3:00-7:00 | Sleep (staggered; someone keeps the build green) | | |
| 7:00-9:00 | Fixes only | Fixes only | Demo video (~1 min), README disclosures, X/LinkedIn post (#AppBuildersPH, tag Cognition/Devin) |
| **9:00** | **Freeze, repo public, submit by 9:30** | | |

---

## 10. Map content (reconstruction)

| Floor | Zones |
|---|---|
| LG | SM Supermarket, Western Union, DHL, Mr. Quickie |
| GF | Starbucks, BDO + ATM, H&M, Kultura, Auntie Anne's, La Botica, SM Store entrance, MRT/One Ayala side |
| 2F | Sfera, Dear Flora, Crocs, Tissot, Wenger, Broadway Gems, Miniso |
| 3F | SM Makati Foodcourt (Kyu Kyu Ramen 99, ...), Goldilocks, Mary Grace, Delifrance, Brownies Unlimited, Sizzling Plate, Cucina Norte, Fuel Burgers, Gong Cha |
| 4F Cyberzone | ASUS, Lenovo Legion, Techno, Mi Store, GameXtreme, Nintendo, **fictional phone-repair stalls** |
| Annex (AX) | SM Appliance Center, Dyson, Pet Express, BOS Shoes & Bags Repair |

Each floor has 2 escalator pairs (up/down separate), 1 elevator through every floor, CRs and an ATM. The bridge links the main building and the Annex. The building outline comes from OpenStreetMap ways 27831200 (SM Makati) and 263667838 (SM Makati Annex).

---

## 11. Out of scope
Beacons/Wi-Fi fingerprinting, live position tracking, voice, camera/photo input, accounts, multiple malls in the UI, offline-on-phone (needs a secure context), cloud anything.

## 12. Risks

| Risk | Mitigation |
|---|---|
| Phones can't reach the laptop | Firewall rule + airplane-mode instruction; tested in the first hour |
| Hotspot subnet changes, so printed QRs break | Server-generated QR; on-screen anchors if the subnet is unstable |
| GPU not used by the runtime on the RX 6600 XT | LM Studio/llama.cpp Vulkan; CPU 3B as fallback |
| The demo machine isn't the desktop | Decide tonight; the 3B CPU path + 6 s fallback keeps it usable |
| LLM emits bad JSON or is slow | Schema-constrained output, 6 s timeout, deterministic fallback |
| Map data late | Engine developed on `data/sample`; validation errors are explicit |
| Low-end phone janks | 150 KB budget, one floor at a time, throttle testing |
| A judge asks "isn't this just a server?" | Edge-box framing + live no-internet demo |

## 13. Testing
Unit tests (pytest) for pure logic only:
- mall validation
- router: directional escalators, elevator-only
- planner: acceptance example + duration flip; order rules; `dropped` / `ready_at`; deadline warning
- trip: `apply_edits` for every op, including the ambiguous-reference question and the fallback duration regex
- locator: disambiguating with two landmarks No integration tests and no UI tests.

## 14. Disclosures (for submission)
- **Models:** chat and embedding models as finally chosen.
- **Runtime:** LM Studio / llama.cpp / Ollama.
- **Frameworks:** FastAPI etc.
- **Map data:** OpenStreetMap building outlines (c OpenStreetMap contributors, ODbL); store names from public listings.
- **Layout:** our own reconstruction.
- **AI dev tools:** Claude Code.
- **Network:** no internet or cloud services at runtime.

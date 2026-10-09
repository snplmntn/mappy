# Smart alternatives: Mappy never dead-ends

Spec (agreed in chat, 2026-10-09): when a shopper asks for a store, brand or item the mall does not
have, Mappy must answer with the closest *useful* alternatives instead of "I couldn't find X", and
this must work for every category (food, cafe, clothing, shoes, beauty, pharmacy, electronics,
banks, ...). The alternatives must feel smart: ranked by what the missing brand is known for
(traits such as "fried chicken", "milk tea", "sneakers"), then by walk time, with a one-sentence
reason. It must also: substitute inside multi-errand plans; nudge toward a nearer same-kind store
when the asked-for store exists but is far; support "show more / iba pa"; and learn on-device
which alternative shoppers pick. Replies stay in English. Everything runs offline on the edge
laptop; the brand knowledge is a rules table so it answers in milliseconds without the LLM.

## Global Constraints

- Python 3.12, FastAPI, pydantic 2. Run tests with `.venv\Scripts\python -m pytest -q` from the
  repo root (Windows). All tests must pass; none may use the network or the real LLM. Tests use the
  fixtures in `server/tests/conftest.py` (`mall` = `data/sample/mall.json`, `search` with
  `HashEmbedder`). The sample mall has categories: phone_repair, shoe_repair, food, cafe, clothing,
  gift, electronics, restroom, and places jollibee-gf, foodcourt-2f (food), starbucks-gf,
  starbucks-2f (cafe), hm-gf (clothing), kultura-gf (gift), techno-2f (electronics).
- `data/sm-makati/mall.json` is the real demo mall (61 places). `server/tests/test_sm_makati_data.py`
  validates it; do not edit the data file in this plan.
- Follow the existing style: small modules with a one-line docstring, module-level constants in
  CAPS, no classes where a function will do, no new dependencies. Keep `chat.py` orchestration-only;
  scoring and tables live in `search.py` / new modules.
- User-facing reply text is English. Store names and category labels come from `CATEGORY_LABELS`
  in `server/mappy/search.py`.
- `result.type == "places"` is rendered by `web/js/cards.js:placesCard` as tappable rows; unknown
  extra keys on a result are ignored by the frontend, so new keys are safe.
- The LLM (`server/mappy/llm.py`) stays an extractor only. Do not add new intents to its schema.
  New intents are rules-only (`server/mappy/rules.py`).
- No integration tests against a DB or external API. No tests for pure UI changes.
- Commit after each task: `type(scope): message` (e.g. `feat(search): ...`). Stage only your own
  changes.

## Current code you build on

- `server/mappy/chat.py`: `ChatService._respond` handles intents. The "find" branch
  (`_find_category`, `_matches`, `_places_result`) and the "plan" branch (`make_errand`) are the
  hook points. `_not_found(queries)` builds the dead-end text. `chat()` re-asks the LLM once when
  rules dead-end (`_dead_end`).
- `server/mappy/search.py`: `CATEGORY_LABELS`, `CATEGORY_WORDS`, `Search.search`,
  `Search.by_category(cat)` (floor-ordered ids), `Search.alias_category(text)`,
  `Search.names_in(text)`, `Search._mentions(alias, text)` (whole-word for short aliases,
  `fuzz.partial_ratio >= 90` otherwise), `_norm(text)`.
- `server/mappy/models.py`: `ErrandReq(query, category)`, `Extraction(intent, errands, edits,
  landmarks, floor, source)`, `Errand`.
- `server/mappy/api.py`: `/api/chat` adds `meta.ms` and `meta.model`, records to `EdgeMonitor`.
- `web/js/main.js` `actions.send` posts `{message, at, now, trip}`; `actions.navigateToPlace(id)`.
  `web/js/chat.js` `receipt(meta)` renders the engine line under each bot message.

---

## Task 1: Brand and trait knowledge table

**Files:** create `server/mappy/brands.py`; create `server/tests/test_brands.py`.

Create a rules table of well-known brands mapped to the app's categories and a few traits each.

```python
"""What well-known brands are, so a missing store can be answered with the nearest thing like it.
Categories are the app's own (see search.CATEGORY_LABELS); traits are plain words that also appear
in place tags, so alternatives can be ranked by what the shopper was really after."""

from dataclasses import dataclass

from rapidfuzz import fuzz

SHORT_ALIAS_LEN = 5


@dataclass(frozen=True)
class Brand:
    name: str          # display name, e.g. "Jollibee"
    category: str      # one of CATEGORY_LABELS keys
    traits: tuple[str, ...]
    aliases: tuple[str, ...] = ()   # extra spellings/nicknames, lowercase: ("mcdo", "mcdonalds")


BRANDS: tuple[Brand, ...] = (...)   # see coverage below


def brand_in(text: str) -> Brand | None:
    """The brand a short request names, matched by full name or alias (typo-tolerant), else None.
    Longest alias wins so "coffee bean" does not lose to "bean"."""


def traits_of(name: str) -> tuple[str, ...]:
    """Traits for an exact brand/store name (case-insensitive), or () when unknown. Used to rank
    alternatives for a store that exists but is far (Task 4)."""
```

Matching rule for `brand_in` (mirror `Search._mentions`): normalize both sides to lowercase, strip
punctuation except `&` and `'`; for an alias of length `<= SHORT_ALIAS_LEN` require a whole-word
match; otherwise `fuzz.partial_ratio(alias, text) >= 90`. Check aliases longest-first across all
brands. The display `name` is itself an alias.

Coverage (at least these; add more if you know them, Philippine mall chains first). Traits are
lowercase words/phrases; prefer words that already appear in mall tags (`chicken`, `burger`,
`milk tea`, `coffee`, `pastry`, `bakery`, `cake`, `dessert`, `ice cream`, `ramen`, `japanese`,
`korean`, `pasta`, `pizza`, `shawarma`, `sandwich`, `bread`, `sneakers`, `sandals`, `shoes`,
`fashion`, `skincare`, `makeup`, `medicine`, `vitamins`, `watch`, `jewelry`, `phone`, `laptop`,
`gadget`, `games`, `console`, `appliance`, `books`, `school supplies`, `gift`, `souvenir`,
`home`, `kitchen`, `pet`, `grocery`, `withdraw`, `remittance`, `package`).

- food: Jollibee (fried chicken, burger, spaghetti, fast food; aliases jabee, jolibee), McDonald's
  (aliases mcdo, mcdonalds, mcdonald), KFC, Mang Inasal (chicken, filipino, rice), Chowking
  (chinese, noodles, halo-halo), Greenwich (pizza, pasta), Shakey's (pizza), Pizza Hut, Yellow
  Cab, Burger King, Wendy's, Army Navy (burger, burrito), Max's Restaurant (chicken, filipino),
  Kenny Rogers (chicken), BonChon (chicken, korean), Tokyo Tokyo (japanese), Pepper Lunch, Ramen
  Nagi (ramen), Pancake House, Tim Hortons is cafe, Dunkin (donut, coffee) cafe, Krispy Kreme
  (donut) cafe, Red Ribbon (cake, bakery), Goldilocks (cake, bakery), Chatime (milk tea),
  Macao Imperial (milk tea), Serenitea (milk tea), Dairy Queen (ice cream, dessert), Potato
  Corner (fries, snack), Andok's (chicken), Samgyupsalamat (korean, bbq), Zark's (burger),
  Subway (sandwich), Taco Bell, Sbarro (pizza), Classic Savory (chicken), Conti's (cake,
  bakery), Shawarma Shack (shawarma), Mister Donut (donut), Starbucks (cafe), Coffee Bean &
  Tea Leaf (cafe; aliases coffee bean, cbtl), Seattle's Best (cafe), Bo's Coffee (cafe),
  UCC (cafe), Tim Hortons (cafe), Figaro (cafe), Mary Grace (cafe, ensaymada), Delifrance (cafe).
- clothing: Uniqlo, H&M, Zara, Bench, Penshoppe, Forever 21, Cotton On, Mango, Giordano, Oxygen,
  Levi's (jeans), Lacoste, Guess, Old Navy, Gap, Terranova, Regatta.
- shoes: Nike (sneakers, sportswear), Adidas (sneakers, sportswear), Skechers, Converse, Vans,
  Crocs (sandals), Havaianas (sandals, tsinelas), World Balance, Payless, Toms, Birkenstock, Puma,
  New Balance.
- accessories: Pandora (jewelry), Swatch (watch), Casio (watch), Fossil (watch), Lovisa, Charles &
  Keith (bag), Sunnies Studios (sunglasses, eyeglasses), Owndays (eyeglasses).
- beauty: Watsons (skincare, medicine, vitamins), Sephora (makeup), The Body Shop (skincare),
  Innisfree (skincare, korean), Nature Republic, Etude House, Beauty Bar, Kiehl's, MAC, Colourette,
  Human Nature, BYS.
- pharmacy: Mercury Drug (medicine, vitamins), Southstar Drug, Rose Pharmacy, Generika, TGP.
- electronics: Power Mac Center (apple, phone, laptop), Samsung, Apple, Huawei, Oppo, Vivo,
  Realme, Xiaomi, Silicon Valley, Octagon, Digital Walker, Beyond the Box, PC Express, Datablitz
  (games, console) gaming, Toy Kingdom (toys) gift, Toys R Us (toys) gift.
- books_stationery: National Book Store (aliases national bookstore, nbs), Fully Booked, Powerbooks.
- grocery: SM Supermarket, Robinsons Supermarket, Landers, S&R, 7-Eleven (aliases 7 eleven,
  7-11, 711, seven eleven; traits snack, convenience), Ministop, FamilyMart, Alfamart.
- department_store: SM Store, Rustan's, Landmark, Robinsons Department Store, Metro.
- home: Miniso, Daiso, Muji, IKEA, Ace Hardware, Wilcon, True Value, Our Home, SM Home.
- bank: BDO, BPI, Metrobank, Landbank, UnionBank, Security Bank, RCBC, PNB, Chinabank, EastWest.
- atm: (no brands; "atm" is already a category word)
- remittance: Western Union, Palawan Express, Cebuana Lhuillier, MLhuillier, GCash, Maya.
- courier: LBC, JRS Express, J&T Express, DHL, FedEx, 2GO, Grab Express.
- pet: Pet Express, Pet Lovers Centre, Bow & Wow, Dogs and the City.
- gaming: Datablitz, GameXtreme, iTech, Nintendo, PlayStation (console), Timezone (arcade).
- appliances: Abenson, Anson's, Automatic Centre, Western Appliances, Dyson, SM Appliance.
- gift: Papemelroti, Kultura, Hallmark, Typo.
- cafe: Tim Hortons, Dunkin, Krispy Kreme, Starbucks, Coffee Bean, Seattle's Best, Bo's Coffee,
  UCC, Figaro, Mary Grace, Delifrance, Kumori (bakery, japanese), Tiger Sugar (milk tea),
  Gong Cha (milk tea).

Brand names that also exist as stores in a mall (Starbucks, Uniqlo, BDO, ...) are fine to list:
the table is consulted only after name search found nothing, and traits of present brands are
reused by Task 4.

Tests (`server/tests/test_brands.py`):
- `brand_in("take me to jollibee").category == "food"` and name == "Jollibee".
- `brand_in("mcdo")` and `brand_in("jolibee")` resolve (alias and typo).
- `brand_in("coffee bean")` returns "Coffee Bean & Tea Leaf", not something shorter.
- `brand_in("may uniqlo ba dito").category == "clothing"`; `brand_in("mercury drug").category == "pharmacy"`;
  `brand_in("nike").category == "shoes"`; `brand_in("lbc").category == "courier"`.
- `brand_in("zzyzx emporium") is None`; `brand_in("food") is None` (category words are not brands).
- Every `Brand.category` is a key of `search.CATEGORY_LABELS`; every alias is lowercase; names are
  unique.
- `traits_of("Jollibee")` contains "chicken"; `traits_of("Unknown") == ()`.

---

## Task 2: Alternatives for a missing store (find + plan + add)

**Files:** `server/mappy/search.py`, `server/mappy/chat.py`, `server/tests/test_search.py`,
`server/tests/test_chat.py`.

### 2a. Ranking in `search.py`

```python
def trait_score(self, pid: str, traits: tuple[str, ...]) -> int:
    """How many of the traits a place matches, by whole word/phrase in its tags or name."""

def alternatives(self, category: str, traits: tuple[str, ...], exclude: tuple[str, ...] = ()) -> list[str]:
    """Places of a category ranked by trait overlap (desc), then floor order; `exclude` ids are dropped."""
```

`alternatives` starts from `by_category(category)` so the tie-break stays floor order; the chat
layer applies walk time.

### 2b. Chat layer

Constants: `ALT_RESULTS = 5` (reuse `FIND_RESULTS`), no new magic numbers.

Add to `ChatService`:

```python
def _alternative_category(self, req: ErrandReq) -> tuple[str, str, tuple[str, ...]] | None:
    """(display name, category, traits) to list when nothing matched `req.query`: the brand table
    first, then the LLM's category guess; None when this mall has no such category."""
```
- brand = `brand_in(req.query)`; if brand and `self.search.by_category(brand.category)`:
  return `(brand.name, brand.category, brand.traits)`.
- elif `req.category` and `self.search.by_category(req.category)`:
  return `(req.query, req.category, ())`.
- else None.

```python
def _alternatives_result(self, name: str, category: str, traits, start, router, exclude=()) -> dict:
```
- `ids = self.search.alternatives(category, traits, exclude)`.
- Build rows like `_places_result` but sort by `(-trait_score, walk_min is None, walk_min)` and cap
  at `FIND_RESULTS`. Refactor `_places_result` to take an optional `scores: dict[str, int] | None`
  so both paths share one row builder (DRY), rather than duplicating the row loop.
- Return `{"type": "places", "query": name, "category": category, "alternatives_for": name,
  "places": rows}`.

```python
def _alternatives_reply(self, name: str, category: str, traits, rows: list[dict]) -> str:
```
Format, exactly:
- Base: `No {name} in this mall, but here are other {label} places.` where `label =
  CATEGORY_LABELS[category].lower()` (e.g. "food", "coffee", "clothes").
- If any row has trait score > 0: append ` {A} and {B} also do {traits}.` where A, B are the names
  of the first two rows with score > 0 (just `{A}` if only one), and `{traits}` is the matched
  traits of row A joined with " and " (max 2 traits). E.g. `Turks and Fuel Burgers also do chicken
  and burger.`
- If the first row has `walk_min`: append ` {first.name} is {walk_min} min away.`

Hook points in `_respond`:
- "find" branch: when `ids` is empty, `alt = self._alternative_category(req)`; if alt:
  `result = self._alternatives_result(...)`, `reply = self._alternatives_reply(...)`, return
  `{"reply", "result", "trip"}`. Else keep `_text(_not_found(...))`.
- "plan" branch: replace the `make_errand` call with a new
  `self._errand_or_alternative(req.query, req.category, new_id) -> tuple[Errand | None, str | None]`
  that returns `(errand, None)` on a normal match, `(errand, brand_name)` when it substituted
  (errand label = category label, candidates = `search.alternatives(...)[:CANDIDATES]`, duration
  from the first candidate as in `make_errand`), `(None, None)` when nothing. Collect substituted
  names in `swapped`; append to the plan reply: ` No {A} here, so I added other {label} places
  instead.` (one sentence per swapped name; label as above). `make_errand` (used by `apply_edits`
  for "add" edits and `/api/plan`) becomes a thin wrapper returning only the errand, so adding a
  missing brand to a plan also substitutes.

The dead-end LLM retry in `chat()` stays as is; an alternatives result is `type == "places"` so it
is not a dead end.

### Tests
`test_search.py`:
- `alternatives("food", ("chickenjoy",))` on the sample mall puts `jollibee-gf` before
  `foodcourt-2f`; with traits `("ramen",)` the order flips.
- `alternatives("food", (), exclude=("jollibee-gf",))` omits it.

`test_chat.py` (use `svc(mall, search)` with no LLM and `FixedLLM` as existing tests do; look at
`AT` and `run`):
- `"mcdo"` (rules path, no LLM): result type "places", `alternatives_for == "McDonald's"`,
  all places have category "food", reply starts with `No McDonald's in this mall, but here are
  other food places.` and ends with ` min away.`; `meta.engine == "rules"`.
- `"zara"` → clothing places (hm-gf); `"watsons"` → sample mall has no beauty → still
  `"couldn't find"` text (category absent).
- LLM backstop: `FixedLLM(Extraction(intent="find", source="llm", errands=[ErrandReq(query="Zzyzx
  Burgers", category="food")]))` with message `"saan ang Zzyzx Burgers dito"` → places result of
  food with `alternatives_for == "Zzyzx Burgers"`.
- Existing `test_chat_unknown_store_says_not_found` (no category) must still pass unchanged.
- Plan: `"mcdo, phone repair"` (rules plan path splits on comma; if rules don't make a plan from
  this, use `FixedLLM` with a plan Extraction) → plan has 2 errands, one with category "food"
  whose candidates are sample food places, and the reply contains `No McDonald's here, so I added
  other food places instead.`
- Trait sentence: message `"jabee"` against a `FixedLLM`-free service, sample mall — jollibee-gf
  exists so this is a *name* hit, not alternatives; instead assert the trait sentence using a
  brand whose traits match sample tags, e.g. `"ramen nagi"` → reply contains
  `also do ramen` and the first place is `foodcourt-2f`.

---

## Task 3: Receipt line says "on-device"

**Files:** `web/js/chat.js` only. No tests (pure UI text).

In `receipt(meta)` change the engine strings to:
- rules: `` `On-device · instant match · ${seconds(meta.ms)} · nothing sent online` ``
- llm: `` `On-device · ${meta.model} · ${seconds(meta.ms)} · nothing sent online` ``
- cache: `` `On-device · remembered answer · ${seconds(meta.ms)}` ``
- fallback: `` `On-device · quick parser (AI was busy) · ${seconds(meta.ms)}` ``

Commit as `feat(web): say on-device in the receipt line`.

---

## Task 4: Nearer same-kind store when the asked-for one is far

**Files:** `server/mappy/chat.py`, `server/tests/test_chat.py`.

Constant `NUDGE_MIN = 4` (minutes closer before we mention another store).

In the "find" branch, only when the result came from a *name* match (`cat` is None and `ids`
non-empty): let `top = rows[0]` after walk-time sorting. Compute
`traits = traits_of(top.name) or tuple(self.mall.places[top.id].tags)`, then
`near = self.search.alternatives(top.category, traits, exclude=tuple(ids))` with walk times; pick
the first `near` row whose `walk_min` is not None and `<= top.walk_min - NUDGE_MIN`. If found,
append that row to `result.places` (keep it last, mark it with `"nudge": True`) and extend the
reply: `Here's what I found for “{q}”: {top.name} is {top.walk_min} min away on {top.floor_name}.
{near.name} on {near.floor_name} does {trait or label} too, {near.walk_min} min.` where
`{trait or label}` is the first matched trait, else the lowercase category label.

Tests: build a service on the sample mall and pick a start anchor so that one cafe is far and the
other near (sample has starbucks-gf and starbucks-2f: both the same brand, so use a query that
name-matches one specific store far from `AT`, and a same-category store near; read
`data/sample/mall.json` and `conftest.py` to choose `at`). If the sample geometry cannot produce a
≥4 min gap, monkeypatch `ChatService._walk_min` in the test to return fixed minutes per place id.
Assert: the nudge row is last with `nudge == True`, and the reply contains `does` and `too,`.
Also assert no nudge when the gap is below `NUDGE_MIN`.

---

## Task 5: "Show more / iba pa"

**Files:** `server/mappy/models.py`, `server/mappy/rules.py`, `server/mappy/chat.py`,
`server/mappy/api.py`, `web/js/main.js`, `web/js/state.js`, `server/tests/test_rules.py`,
`server/tests/test_chat.py`.

- `Extraction.intent` Literal gains `"more"`. Do NOT add it to the LLM schema in `llm.py`.
- `rules.py`: `MORE_RE = re.compile(r"^\s*(?:iba pa|iba pang|yung iba|meron pa|may iba pa|ano pa|"
  r"show more|more|others?|something else|next)\b", re.I)`; in `parse`, right after `OTHER_RE`,
  return `Extraction(intent="more")` on match.
- `api.py`: `ChatReq` gains `prev: dict | None = None` (the last `places` result the phone showed:
  `{query, category, alternatives_for?, places:[{id,...}]}`). Pass it through to
  `svc.chat(message, at, now, trip, prev)`.
- `chat.py`: `chat(..., prev: dict | None = None)`; `_respond` gets `prev`. New branch for
  `intent == "more"`:
  - if `prev` is None or has no `category`: `_text("Ask for a store or a type first, then say “more”.", trip)`.
  - else `shown = tuple(p["id"] for p in prev["places"])`,
    `ids = search.alternatives(prev["category"], traits, exclude=shown)` where traits come from
    `brand_in(prev.get("alternatives_for") or "")` if any else `()`. If empty:
    `_text(f"That's every {label} place in this mall.", trip)`. Else return a places result (same
    builder as Task 2, carrying `category` and `alternatives_for` forward) with reply
    `More {label} places:`.
  - Every `places` result (plain find too) must now carry `"category"`: the listed category for a
    category listing, else the top place's category.
- Frontend: `state.js` adds `lastPlaces: null` (not persisted). `main.js` `actions.send` sends
  `prev: state.lastPlaces`; after a bot reply with `res.result.type === "places"`, `update({
  lastPlaces: res.result })`.
- `meta.intent` for this path is "more" (already flows through `edge.record`).

Tests:
- `test_rules.py`: `parse("iba pa", Trip(), search).intent == "more"`, same for "show more";
  `parse("more coffee", ...)` is NOT "more" (it is a find; `MORE_RE` must only match when the
  message is just the cue: use `\s*$` after the group).
- `test_chat.py`: first `"food"` → places result with `category == "food"`; then `"iba pa"` with
  `prev=` that result → the new places exclude the shown ids (sample has 2 food places, so show
  the second); then `"iba pa"` again with both shown → text containing "every food place".
  Without `prev` → text containing "first".

---

## Task 6: On-device learning of picked alternatives

**Files:** create `server/mappy/learn.py`; `server/mappy/api.py`; `server/mappy/chat.py`;
`web/js/main.js`; `web/js/cards.js`; create `server/tests/test_learn.py`; `server/tests/test_chat.py`.

```python
"""What shoppers picked when a brand was missing, so the next shopper sees that store first.
Counts only (brand -> place id -> picks); no phone identity. Saved as JSON on the edge laptop."""

class Picks:
    def __init__(self, path: Path | None): ...   # loads if the file exists; None = memory only
    def record(self, asked: str, place_id: str) -> None  # asked is normalized lowercase; saves
    def ranked(self, asked: str) -> list[str]            # place ids by pick count desc
    def top(self, asked: str) -> str | None
```
- File: `settings.cache_dir / "picks.json"`, written atomically (write `.tmp` then `replace`).
- `ChatService` gains a `picks: Picks` field (default `Picks(None)` so existing tests and
  constructors keep working; `api.py` passes `Picks(settings.cache_dir / "picks.json")`).
- `_alternatives_result`: after trait sorting, move ids in `picks.ranked(name)` to the front in
  that order. If `picks.top(name)` is a listed place, prefix the reply with
  `Shoppers here usually pick {store} instead of {name}. ` (before the "No {name} in this mall…"
  sentence).
- `api.py`: `POST /api/pick` body `{asked: str (1..80), place: str}`; 404-style error if the
  place id is unknown; records and returns `{"ok": true}`.
- Frontend: `cards.js` `placesCard` — when `result.alternatives_for` is set, the row's onclick
  first calls `actions.pickAlternative(result.alternatives_for, p.id)` then navigates.
  `main.js` adds `pickAlternative(asked, place)` that fire-and-forgets `post("/api/pick", ...)`
  (catch and ignore errors).

Tests:
- `test_learn.py` (use `tmp_path`): record twice for one store and once for another → `ranked`
  order; persists across a new `Picks(path)` instance; `Picks(None)` works in memory; unknown
  brand → `[]` / `None`.
- `test_chat.py`: service with `Picks(None)` where `foodcourt-2f` was picked for "mcdo" → the
  "mcdo" alternatives list has `foodcourt-2f` first and the reply starts with `Shoppers here
  usually pick`.
- `test_api_*`: one TestClient test that `POST /api/pick` with a valid place returns ok and an
  unknown place returns a 4xx (look at how existing api tests build the app in
  `test_api_version.py`).

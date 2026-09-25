# KEYSTROKE QUEST - build contract

This file is the single source of truth while four agents build in parallel.
**Do not edit files you do not own. Do not change any signature or DOM id defined here.**

## File ownership

- Agent 1 (backend): `curriculum.py`, `db.py`, `progress.py`
- Agent 2 (AI): `ai.py`, `story.py`, `data/wordlist.txt`
- Agent 3 (retro UI): `static/css/retro.css`, `static/fonts/*`, `templates/title.html`, `templates/map.html`, `templates/stage.html`, `templates/results.html`, `templates/stats.html`
- Agent 4 (game engine): `static/js/engine.js`, `static/js/keyboard.js`, `static/js/game.js`, `static/js/dialogue.js`, `static/js/audio.js`
- Owned by the lead (already written): `app.py`, `config.py`, `templates/base.html`, `requirements.txt`, `.env.example`

## Game structure

5 worlds, each with 5 stages plus a boss stage. Key order follows the TypingClub
progression: home row `fj dk sl a; gh`, top row `ru ei wo qp ty`, bottom row
`vm c, x. z/ bn`, then Shift/capitals, then punctuation and numbers.

Stage ids are integers, ordered, starting at 1. Boss stages have `is_boss = True`.

---

## Python contract (Agent 1)

### `curriculum.py`

```python
FINGER_MAP: dict[str, dict]      # 'f' -> {"hand": "left", "finger": "index"}
                                 # finger is one of: pinky ring middle index thumb

@dataclass
class Stage:
    id: int
    world_id: int
    index_in_world: int          # 1-based
    title: str                   # "F and J"
    new_keys: str                # "fj"
    allowed_keys: str            # every key unlocked so far, incl. space
    mode: str                    # "drill" | "words" | "sentences" | "boss"
    goal_wpm: int
    goal_accuracy: float         # 0.0-1.0
    is_boss: bool

@dataclass
class World:
    id: int
    title: str                   # "The Home Row Dojo"
    subtitle: str
    theme: str                   # css theme key: dojo | tower | undergrid | citadel | harbor
    boss_name: str               # "Sensei Semicolon"
    boss_hp: int
    stage_ids: list[int]

WORLDS: list[World]
STAGES: list[Stage]

def get_stage(stage_id: int) -> Stage | None
def get_world(world_id: int) -> World | None
def next_stage_id(stage_id: int) -> int | None
def stage_dict(stage: Stage) -> dict       # JSON-safe
def world_dict(world: World) -> dict       # JSON-safe
def finger_for(char: str) -> dict          # falls back to a sane default
```

### `db.py`

```python
def init_db() -> None                      # idempotent, creates all tables
def get_conn() -> sqlite3.Connection       # row_factory = sqlite3.Row

def record_run(stage_id, wpm, raw_wpm, accuracy, duration_ms,
               combo_max, hp_left, xp) -> int          # returns run id
def upsert_keystats(keystrokes: list[dict]) -> None
    # keystroke = {"expected": "f", "typed": "d", "ms": 180}
def mark_passed(stage_id, wpm, accuracy, stars) -> None

def get_progress() -> dict
    # {"stages": {stage_id: {"passed": bool, "best_wpm": float,
    #                        "best_accuracy": float, "stars": int}},
    #  "unlocked_max": int}
def get_player() -> dict                   # {"level": int, "xp": int, "settings": dict}
def add_xp(amount: int) -> dict            # returns updated player dict
def save_settings(settings: dict) -> None

def get_weak_keys(limit: int = 5) -> list[dict]
    # [{"key": "q", "accuracy": 0.71, "finger": "pinky", "hand": "left",
    #   "avg_ms": 420, "attempts": 34}]  -- worst first, min 5 attempts
def get_key_heatmap() -> list[dict]        # same shape, every practiced key
def get_wpm_history(limit: int = 50) -> list[dict]   # [{"created_at", "wpm", "accuracy"}]

def cache_get(key: str) -> dict | None     # entries older than 7 days are ignored
def cache_set(key: str, payload: dict) -> None
```

### `progress.py`

```python
def passed(stage, wpm: float, accuracy: float) -> bool
def stars_for(stage, wpm: float, accuracy: float) -> int        # 0-3
def rank_for(stage, wpm: float, accuracy: float, combo_max: int) -> str   # "S"|"A"|"B"|"C"|"D"
def xp_for_run(stage, wpm, accuracy, combo_max, hp_left) -> int
def level_for_xp(xp: int) -> dict
    # {"level": int, "xp_into_level": int, "xp_for_next": int, "progress": 0.0-1.0}
```

---

## Python contract (Agent 2)

### `ai.py`

Every function must be safe to call with no API key and no internet: catch all
exceptions and return the offline fallback instead of raising.

```python
def is_ai_enabled() -> bool

def generate_lines(*, allowed_keys: str, new_keys: str, mode: str,
                   weak_keys: list[str], count: int) -> dict
    # returns {"lines": ["fjf jfj fff", ...], "source": "groq"|"fallback"}
    # EVERY character of every line must be inside allowed_keys (plus space).
    # Validate server-side and drop bad lines; top up from the fallback
    # generator so exactly `count` lines are always returned.

def generate_dialogue(*, world, stage, kind: str, context: dict) -> dict
    # kind: "intro" | "outro" | "boss_intro" | "boss_win" | "boss_lose"
    # returns {"lines": [{"speaker": "Sensei Semicolon",
    #                     "portrait": "boss",      # hero | npc | boss | narrator
    #                     "text": "..."}],
    #          "source": "groq"|"fallback"}
    # 1-3 lines, each under 140 characters, no emoji, plain ASCII only.

def generate_boss_line(*, world, context: dict) -> dict
    # returns {"line": "...", "source": ...}; under 80 chars.
```

### `story.py`

```python
WORLD_LORE: dict[int, dict]     # per world: setting, hero_name, npc_name,
                                # boss_name, tone, plus hand-written fallback lines
def fallback_dialogue(world_id: int, stage, kind: str) -> list[dict]
def fallback_boss_line(world_id: int, context: dict) -> str
def fallback_lines(allowed_keys: str, new_keys: str, mode: str,
                   weak_keys: list[str], count: int) -> list[str]
    # deterministic offline generator; uses data/wordlist.txt filtered by allowed_keys
```

---

## HTTP API (already implemented in `app.py`)

- `GET  /` -> title screen
- `GET  /map` -> world map
- `GET  /stage/<int:stage_id>` -> stage screen
- `GET  /stats` -> player card
- `GET  /api/stage/<int:stage_id>` ->
  ```json
  {"stage": {...}, "world": {...}, "lines": ["..."], "weak_keys": ["q","z"],
   "dialogue": {"intro": [...], "outro": [...]}, "source": "groq",
   "finger_map": {"f": {"hand": "left", "finger": "index"}}}
  ```
- `POST /api/session` body
  ```json
  {"stage_id": 1, "wpm": 32.4, "raw_wpm": 35.0, "accuracy": 0.97,
   "duration_ms": 41000, "combo_max": 48, "hp_left": 3,
   "keystrokes": [{"expected": "f", "typed": "f", "ms": 180}]}
  ```
  response
  ```json
  {"passed": true, "stars": 3, "rank": "A", "xp_gained": 120,
   "player": {"level": 4, "xp": 980, "xp_into_level": 80,
              "xp_for_next": 300, "progress": 0.26},
   "next_stage_id": 2, "unlocked": true}
  ```
- `GET  /api/progress` -> `{"player": {...}, "progress": {...}, "weak_keys": [...]}`
- `POST /api/boss-line` body `{"stage_id": 6, "context": {...}}` -> `{"line": "..."}`
- `GET  /api/stats` -> `{"heatmap": [...], "weak_keys": [...], "history": [...], "fingers": [...]}`
- `POST /api/settings` body `{"sound": true, "scanlines": true, "reduced_motion": false}`

---

## Frontend DOM contract (Agents 3 and 4)

Agent 3 writes the markup and CSS. Agent 4 writes JS that finds these exact ids.
Neither may rename them.

### Global

- `#kq-screen` - root wrapper on every page; JS adds `.kq-shake` briefly on a typo
- `#kq-scanlines` - fixed CRT overlay div, toggled by `body.kq-no-scanlines`
- `#kq-sound-toggle` - speaker button, `data-on="true|false"`
- `.kq-btn` - base arcade button; modifiers `.kq-btn--primary`, `.kq-btn--ghost`, `.kq-btn--danger`

### Stage screen (`templates/stage.html`)

- `#kq-stage` with `data-stage-id`, `data-is-boss`
- `#kq-text` - typing surface. Engine injects
  `<span class="kq-word"><span class="kq-char" data-char="f">f</span></span>`
  and toggles `kq-char--correct`, `kq-char--wrong`, `kq-char--current`, `kq-char--extra`
- `#kq-caret` - absolutely positioned caret the engine moves with `transform`
- `#kq-input` - visually hidden input that holds keyboard focus
- `#kq-wpm`, `#kq-accuracy`, `#kq-timer` - HUD readouts (text content only)
- `#kq-hp` - hearts container; game.js fills with `<span class="kq-heart" data-full="true">`
- `#kq-combo` - combo number, `#kq-combo-popup` - the "x12 COMBO" flash element
- `#kq-fx` - absolutely positioned layer for floating damage numbers
- `#kq-boss` - boss panel, only rendered when `data-is-boss="true"`
  - `#kq-boss-sprite` (has `data-boss-theme`), `#kq-boss-hp-fill` (JS sets `style.width`),
    `#kq-boss-name`, `#kq-boss-say` (taunt bubble)
- `#kq-keyboard` - empty mount; keyboard.js renders
  `<div class="kq-key" data-key="f" data-finger="index" data-hand="left">`
  and toggles `kq-key--next`, `kq-key--hit`, `kq-key--miss`
- `#kq-hands` - empty mount; keyboard.js renders
  `<div class="kq-finger" data-hand="left" data-finger="index">`, toggles `kq-finger--active`
- `#kq-dialogue` - overlay, hidden with `[hidden]`; children
  `#kq-dialogue-portrait` (`data-portrait`), `#kq-dialogue-speaker`,
  `#kq-dialogue-text`, `#kq-dialogue-next` (blinking prompt)
- `#kq-results` - overlay, hidden with `[hidden]`; children
  `#kq-results-rank`, `#kq-results-wpm`, `#kq-results-accuracy`,
  `#kq-results-combo`, `#kq-results-xp`, `#kq-results-stars`,
  `#kq-results-retry`, `#kq-results-next`, `#kq-results-map`
- `#kq-loading` - "GENERATING..." panel shown while `/api/stage` is in flight

### JS module globals (Agent 4)

Loaded in this order by `base.html`: `audio.js`, `dialogue.js`, `keyboard.js`, `engine.js`, `game.js`.

```js
window.KQAudio = { init(), setEnabled(bool), key(), error(), combo(n),
                   hit(), levelUp(), blip(), start() }
window.KQDialogue = { play(lines) -> Promise, skip(), isOpen() }
window.KQKeyboard = { mount(fingerMap), highlight(char), flash(char, ok), reset() }
window.TypingEngine = class {
  constructor({ textEl, caretEl, inputEl, lines, onKey, onProgress, onComplete })
  start(); reset(); destroy();
}
window.KQGame = { boot(config) }   // called by stage.html inline script
```

`stage.html` must end with:

```html
<script>KQGame.boot({ stageId: {{ stage_id }} });</script>
```

### Colors (Agent 3 defines, Agent 4 only references)

CSS custom properties on `:root`:
`--kq-ink` (near-black outline), `--kq-bg`, `--kq-sky`, `--kq-green`, `--kq-orange`,
`--kq-red`, `--kq-blue`, `--kq-yellow`, `--kq-white`, `--kq-muted`,
`--kq-correct`, `--kq-wrong`, `--kq-shadow`.

Visual target: 16-bit beat-em-up. Hard black outlines, saturated flat colors,
no gradients except scanlines, `image-rendering: pixelated`, 4px hard button
shadows that collapse on press, `Press Start 2P` for headings and buttons,
`VT323` for body copy. Respect `prefers-reduced-motion`.

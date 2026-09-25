"""Curriculum for KEYSTROKE QUEST: finger map, worlds and stages.

Pure data plus small helpers.  This module imports nothing from the rest of the
app so it can never take part in a circular import.

Key order follows the classic touch-typing progression:
home row -> top row -> bottom row -> Shift/capitals -> punctuation and numbers.
"""

from dataclasses import asdict, dataclass, field

# --------------------------------------------------------------------------
# Finger map
# --------------------------------------------------------------------------

# Standard QWERTY touch-typing assignments, unshifted keys only.
_BASE_FINGERS = {
    ("left", "pinky"): "qaz1",
    ("left", "ring"): "wsx2",
    ("left", "middle"): "edc3",
    ("left", "index"): "rfvtgb45",
    ("right", "index"): "yhnujm67",
    ("right", "middle"): "ik,8",
    ("right", "ring"): "ol.9",
    ("right", "pinky"): "p;/'0-=[]",
}

# A shifted character is struck by the same finger as its unshifted twin; the
# opposite pinky holds Shift.
_SHIFT_PAIRS = {
    "1": "!",
    "2": "@",
    "3": "#",
    "4": "$",
    "5": "%",
    "6": "^",
    "7": "&",
    "8": "*",
    "9": "(",
    "0": ")",
    "-": "_",
    "=": "+",
    "[": "{",
    "]": "}",
    ";": ":",
    "'": '"',
    ",": "<",
    ".": ">",
    "/": "?",
}

DEFAULT_FINGER = {"hand": "right", "finger": "index"}

FINGER_MAP: dict[str, dict] = {}

for (_hand, _finger), _keys in _BASE_FINGERS.items():
    for _key in _keys:
        FINGER_MAP[_key] = {"hand": _hand, "finger": _finger}

# Capitals and shifted punctuation reuse the finger of the base key.
for _key, _shifted in list(_SHIFT_PAIRS.items()):
    if _key in FINGER_MAP:
        FINGER_MAP[_shifted] = dict(FINGER_MAP[_key])
for _key in "abcdefghijklmnopqrstuvwxyz":
    if _key in FINGER_MAP:
        FINGER_MAP[_key.upper()] = dict(FINGER_MAP[_key])

# Either thumb works for the space bar.
FINGER_MAP[" "] = {"hand": "both", "finger": "thumb"}

SPACE = " "


# --------------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------------


@dataclass
class Stage:
    id: int
    world_id: int
    index_in_world: int
    title: str
    new_keys: str
    allowed_keys: str
    mode: str
    goal_wpm: int
    goal_accuracy: float
    is_boss: bool
    blurb: str = ""


@dataclass
class World:
    id: int
    title: str
    subtitle: str
    theme: str
    boss_name: str
    boss_hp: int
    stage_ids: list[int] = field(default_factory=list)
    lore: str = ""


# --------------------------------------------------------------------------
# World / stage source data
# --------------------------------------------------------------------------

# Each stage spec: (title, new_keys, unlock, blurb)
#   new_keys -> what the stage drills (boss and review stages re-drill old keys)
#   unlock   -> keys added to the cumulative pool by this stage
_HOME_ROW = "asdfghjkl;"
_TOP_ROW = "qwertyuiop"
_ALL_LETTERS = "abcdefghijklmnopqrstuvwxyz"
_ALL_CAPS = _ALL_LETTERS.upper()

_WORLD_SPECS = [
    {
        "id": 1,
        "title": "The Home Row Dojo",
        "subtitle": "Plant Eight Fingers",
        "theme": "dojo",
        "boss_name": "Sensei Semicolon",
        "boss_hp": 100,
        "lore": "A silent dojo where every journey starts on the eight keys beneath your fingers.",
        "goal_wpm": [10, 11, 12, 13, 14, 15],
        "stages": [
            (
                "F and J: The Anchors",
                "fj",
                "fj",
                "Index fingers live on F and J - feel for the little bumps and never look down.",
            ),
            (
                "D and K: Middle Guard",
                "dk",
                "dk",
                "Middle fingers tap D and K while the index fingers stay parked at home.",
            ),
            (
                "S and L: Ring Bearers",
                "sl",
                "sl",
                "Ring fingers cover S and L; keep the wrists still and let the fingers move.",
            ),
            (
                "A and Semicolon: Pinky Oath",
                "a;",
                "a;",
                "Pinkies stretch out to A and semicolon, then snap straight back home.",
            ),
            (
                "G and H: Inner Reach",
                "gh",
                "gh",
                "Index fingers slide inward for G and H and return to F and J at once.",
            ),
            (
                "Boss: Sensei Semicolon",
                _HOME_ROW,
                "",
                "The Sensei tests all ten home keys - keep every finger on its own post.",
            ),
        ],
    },
    {
        "id": 2,
        "title": "Skyreach Tower",
        "subtitle": "Climb The Top Row",
        "theme": "tower",
        "boss_name": "The Q-Bit",
        "boss_hp": 140,
        "lore": "A tower of floating platforms cut from the row above the home keys.",
        "goal_wpm": [16, 17, 18, 19, 20, 21],
        "stages": [
            (
                "R and U: First Climb",
                "ru",
                "ru",
                "Index fingers climb one step up from F and J to reach R and U.",
            ),
            (
                "E and I: Sky Steps",
                "ei",
                "ei",
                "Middle fingers reach up from D and K to hit E and I.",
            ),
            (
                "W and O: Ring Ascent",
                "wo",
                "wo",
                "Ring fingers stretch up from S and L for W and O.",
            ),
            (
                "Q and P: Pinky Summit",
                "qp",
                "qp",
                "Pinkies take the longest climb of all, up to Q and P.",
            ),
            (
                "T and Y: Center Spire",
                "ty",
                "ty",
                "Index fingers swing inward and up to cover T and Y.",
            ),
            (
                "Boss: The Q-Bit",
                _TOP_ROW + _HOME_ROW,
                "",
                "The Q-Bit hurls the whole top and home row at you without warning.",
            ),
        ],
    },
    {
        "id": 3,
        "title": "The Undergrid",
        "subtitle": "Dig The Bottom Row",
        "theme": "undergrid",
        "boss_name": "Z-Wraith",
        "boss_hp": 180,
        "lore": "Below the city the lost letters of the bottom row hum in the dark.",
        "goal_wpm": [21, 22, 23, 24, 25, 26],
        "stages": [
            (
                "V and M: Down Below",
                "vm",
                "vm",
                "Index fingers drop straight down from F and J to V and M.",
            ),
            (
                "C and Comma: Low Middles",
                "c,",
                "c,",
                "Middle fingers dip below home for C and the comma.",
            ),
            (
                "X and Period: Ring Dive",
                "x.",
                "x.",
                "Ring fingers dive down to X and the period, then float back up.",
            ),
            (
                "Z and Slash: Pinky Depths",
                "z/",
                "z/",
                "Pinkies reach the deepest corners of the board: Z and slash.",
            ),
            (
                "B and N: The Long Stretch",
                "bn",
                "bn",
                "Index fingers stretch inward and down for B and N - the longest reach.",
            ),
            (
                "Boss: Z-Wraith",
                _ALL_LETTERS,
                "",
                "The Z-Wraith drags every letter of the alphabet out of the dark.",
            ),
        ],
    },
    {
        "id": 4,
        "title": "Shift Citadel",
        "subtitle": "Master The Shift",
        "theme": "citadel",
        "boss_name": "Lord Shift",
        "boss_hp": 220,
        "lore": "A fortress of capital letters where every gate demands a Shift to open.",
        "goal_wpm": [26, 27, 28, 29, 30, 30],
        "stages": [
            (
                "Shift Awakens: F J D K",
                "FJDK",
                "FJDK",
                "Hold Shift with the pinky of the hand that is NOT typing the letter.",
            ),
            (
                "Colon Gate: S L A : G H",
                "SLA:GH",
                "SLA:GH",
                "Right pinky plus left Shift makes the colon; keep the stretch short and snap home.",
            ),
            (
                "Capital Spire: Top Row",
                "TYRUEIWOQP",
                "TYRUEIWOQP",
                "Shift with the opposite pinky while the other hand climbs to the top row.",
            ),
            (
                "Deep Caps: Bottom Row",
                "VMCZNXB",
                "VMCZNXB",
                "Capital bottom-row letters mean a long reach and a held Shift at the same time.",
            ),
            (
                "Mixed Case Mayhem",
                _ALL_CAPS,
                "",
                "Real sentences now: tap Shift only for the capital, then release it instantly.",
            ),
            (
                "Boss: Lord Shift",
                _ALL_CAPS,
                "",
                "Lord Shift mixes upper and lower case, so alternate your Shift pinkies cleanly.",
            ),
        ],
    },
    {
        "id": 5,
        "title": "Glyph Harbor",
        "subtitle": "Glyphs And Numbers",
        "theme": "harbor",
        "boss_name": "The Null Pointer",
        "boss_hp": 280,
        "lore": "A harbor of strange glyphs and numbered crates shipped in from far-off systems.",
        "goal_wpm": [31, 32, 33, 34, 35, 35],
        "stages": [
            (
                "Quote Cove",
                "'\"",
                "'\"",
                "Right pinky owns the quote key; add left Shift for the double quote.",
            ),
            (
                "Question and Bang",
                "?!",
                "?!",
                "Question mark is right pinky plus Shift; the bang is left pinky plus Shift.",
            ),
            (
                "Digits 1 to 5",
                "12345",
                "12345",
                "Reach up two rows: 1 is left pinky, 2 ring, 3 middle, 4 and 5 both index.",
            ),
            (
                "Digits 6 to 0",
                "67890",
                "67890",
                "Right hand takes 6 and 7 on the index, 8 middle, 9 ring, 0 pinky.",
            ),
            (
                "Glyph Soup",
                "-=[]",
                "-=[]",
                "The far right corner belongs to the right pinky: dash, equals and the brackets.",
            ),
            (
                "Boss: The Null Pointer",
                "'\"?!1234567890-=[]",
                "",
                "The Null Pointer throws every glyph and digit at once - trust the reaches.",
            ),
        ],
    },
]


def _dedupe(text: str) -> str:
    """Keep first occurrence of each character, preserving order."""
    seen = set()
    out = []
    for ch in text:
        if ch not in seen:
            seen.add(ch)
            out.append(ch)
    return "".join(out)


def _mode_for(world_id: int, index_in_world: int, is_boss: bool, letters_unlocked: int) -> str:
    if is_boss:
        return "boss"
    if world_id >= 3 and (world_id > 3 or index_in_world >= 3):
        return "sentences"
    if letters_unlocked >= 6:
        return "words"
    return "drill"


def _build():
    worlds: list[World] = []
    stages: list[Stage] = []
    pool = ""  # cumulative unlocked keys, in teaching order
    stage_id = 0

    for spec in _WORLD_SPECS:
        world = World(
            id=spec["id"],
            title=spec["title"],
            subtitle=spec["subtitle"],
            theme=spec["theme"],
            boss_name=spec["boss_name"],
            boss_hp=spec["boss_hp"],
            stage_ids=[],
            lore=spec["lore"],
        )
        for index, (title, new_keys, unlock, blurb) in enumerate(spec["stages"], start=1):
            stage_id += 1
            is_boss = index == len(spec["stages"])
            pool = _dedupe(pool + unlock)
            letters = len({c for c in pool if c.isalpha()})
            stages.append(
                Stage(
                    id=stage_id,
                    world_id=world.id,
                    index_in_world=index,
                    title=title,
                    new_keys=new_keys,
                    allowed_keys=pool + SPACE,
                    mode=_mode_for(world.id, index, is_boss, letters),
                    goal_wpm=spec["goal_wpm"][index - 1],
                    goal_accuracy=0.90 if is_boss else 0.95,
                    is_boss=is_boss,
                    blurb=blurb,
                )
            )
            world.stage_ids.append(stage_id)
        worlds.append(world)

    return worlds, stages


WORLDS, STAGES = _build()

_STAGES_BY_ID = {s.id: s for s in STAGES}
_WORLDS_BY_ID = {w.id: w for w in WORLDS}


# --------------------------------------------------------------------------
# Lookups
# --------------------------------------------------------------------------


def get_stage(stage_id: int) -> Stage | None:
    try:
        return _STAGES_BY_ID.get(int(stage_id))
    except (TypeError, ValueError):
        return None


def get_world(world_id: int) -> World | None:
    try:
        return _WORLDS_BY_ID.get(int(world_id))
    except (TypeError, ValueError):
        return None


def next_stage_id(stage_id: int) -> int | None:
    stage = get_stage(stage_id)
    if stage is None:
        return None
    nxt = stage.id + 1
    return nxt if nxt in _STAGES_BY_ID else None


def stage_dict(stage: Stage) -> dict:
    if stage is None:
        return {}
    return asdict(stage)


def world_dict(world: World) -> dict:
    if world is None:
        return {}
    data = asdict(world)
    data["stage_ids"] = list(world.stage_ids)
    return data


def finger_for(char: str) -> dict:
    """Hand and finger for a character; unknown characters get a sane default."""
    if not isinstance(char, str) or len(char) != 1:
        return dict(DEFAULT_FINGER)
    return dict(FINGER_MAP.get(char) or FINGER_MAP.get(char.lower()) or DEFAULT_FINGER)

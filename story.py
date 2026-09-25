"""Offline story content and the offline text generator for KEYSTROKE QUEST.

Nothing in this module touches the network. `ai.py` falls back to everything in
here whenever Groq is missing, slow, broken, or simply lying about the alphabet.

Two jobs:

1. `WORLD_LORE` - hand-written 16-bit RPG flavour for all five worlds, with
   several alternative takes on every dialogue beat so replays differ.
2. `fallback_lines` - a deterministic drill/word generator that is physically
   incapable of emitting a character outside `allowed_keys`.
"""

from __future__ import annotations

import hashlib
import itertools
import random
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
WORDLIST_PATH = BASE_DIR / "data" / "wordlist.txt"

PORTRAITS = ("hero", "npc", "boss", "narrator")
DIALOGUE_KINDS = ("intro", "outro", "boss_intro", "boss_win", "boss_lose")

MAX_DIALOGUE_CHARS = 140
MAX_BOSS_LINE_CHARS = 80
LINE_MIN_CHARS = 30
LINE_MAX_CHARS = 55

# Rough hand split, used to alternate hands inside drill clusters. `ai.py` and
# `story.py` must not import curriculum (Agent 1 owns it), so this is local.
_LEFT_KEYS = set("qwertasdfgzxcvb12345`~!@#$%")
_RIGHT_KEYS = set("yuiophjklnm;',./[]\\-=67890^&*()_+{}|:\"<>?")

_KEY_NAMES = {
    ";": "SEMICOLON",
    ",": "COMMA",
    ".": "PERIOD",
    "/": "SLASH",
    "'": "APOSTROPHE",
    "-": "DASH",
    "=": "EQUALS",
    " ": "SPACE",
}

# Rotating salt so two identical calls in a row do not produce identical text.
_salt = itertools.count()


# --------------------------------------------------------------------------
# World lore
# --------------------------------------------------------------------------

WORLD_LORE = {
    1: {
        "setting": (
            "A bamboo dojo balanced on eight giant keycaps above a koi pond. "
            "Students kneel in rows and press their index fingers into the twin "
            "bumps of F and J until the bumps press back."
        ),
        "hero_name": "the Typist",
        "npc_name": "Master Asdf",
        "boss_name": "Sensei Semicolon",
        "tone": (
            "Serene martial-arts mentor comedy. Short koans, dry humor, and "
            "every single thing is secretly a lesson about posture."
        ),
        "dialogue": {
            "intro": [
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "The dojo gate slides open. A bamboo fountain drips in perfect rhythm."},
                    {"portrait": "npc", "speaker": "Master Asdf",
                     "text": "Today you learn {keys}. Place your fingers home and do not look down. The keys know when you peek."},
                    {"portrait": "hero", "speaker": "the Typist",
                     "text": "I will not look down. Probably."},
                ],
                [
                    {"portrait": "npc", "speaker": "Master Asdf",
                     "text": "Again. {keys}, and breathe. A student who rushes the home row spends a lifetime hunting for it."},
                    {"portrait": "hero", "speaker": "the Typist",
                     "text": "Hunting builds character."},
                    {"portrait": "npc", "speaker": "Master Asdf",
                     "text": "Hunting builds typos."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "A training scroll unrolls across the mat: {stage}."},
                    {"portrait": "npc", "speaker": "Master Asdf",
                     "text": "Feel for the bumps. Two small hills in a flat world. Anchor there and the rest of the board comes to you."},
                ],
            ],
            "outro": [
                [
                    {"portrait": "npc", "speaker": "Master Asdf",
                     "text": "Your hands stayed home. The koi are impressed, and koi are notoriously hard to impress."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "The fountain drips on. It is, you notice, exactly your rhythm now."},
                    {"portrait": "npc", "speaker": "Master Asdf",
                     "text": "Do not let that go to your head. Let it go to your fingers."},
                ],
                [
                    {"portrait": "npc", "speaker": "Master Asdf",
                     "text": "Adequate. In dojo terms that is a standing ovation."},
                    {"portrait": "hero", "speaker": "the Typist",
                     "text": "I will take it."},
                ],
            ],
            "boss_intro": [
                [
                    {"portrait": "boss", "speaker": "Sensei Semicolon",
                     "text": "I am the pause between thoughts, Typist. The pinky's burden. Reach for me and your whole hand must agree to it."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "A single mark hovers at the end of the mat, patient as punctuation."},
                    {"portrait": "boss", "speaker": "Sensei Semicolon",
                     "text": "Others end their lines. I merely continue them. Show me {keys} and show me properly."},
                ],
                [
                    {"portrait": "boss", "speaker": "Sensei Semicolon",
                     "text": "Your index fingers are trained. Cute. I am a pinky problem."},
                    {"portrait": "hero", "speaker": "the Typist",
                     "text": "My pinky has been waiting years for this."},
                ],
            ],
            "boss_win": [
                [
                    {"portrait": "boss", "speaker": "Sensei Semicolon",
                     "text": "Struck down by a well-anchored hand. I concede; and I rarely concede."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "Sensei Semicolon splits neatly into a dot and a comma, then bows to both halves."},
                    {"portrait": "npc", "speaker": "Master Asdf",
                     "text": "The dojo is yours, Typist. Now wipe the mat."},
                ],
                [
                    {"portrait": "boss", "speaker": "Sensei Semicolon",
                     "text": "Go. Climb. The tower will not be nearly this polite."},
                ],
            ],
            "boss_lose": [
                [
                    {"portrait": "boss", "speaker": "Sensei Semicolon",
                     "text": "Your pinky faltered. Rest, stretch, return. The mat is not going anywhere."},
                ],
                [
                    {"portrait": "npc", "speaker": "Master Asdf",
                     "text": "Defeat is only feedback wearing a frightening mask. Again, from home."},
                ],
                [
                    {"portrait": "boss", "speaker": "Sensei Semicolon",
                     "text": "Do not sulk. Even I was once a mere comma."},
                ],
            ],
        },
        "boss_lines": [
            "Your pinky trembles. I felt it.",
            "Anchor, Typist. Anchor.",
            "That was a comma at best.",
            "Breathe. Then miss again, slower.",
            "The bumps are right there.",
            "Posture, Typist. Posture.",
            "You looked down. I saw you look down.",
            "Half a pause is a whole mistake.",
        ],
    },
    2: {
        "setting": (
            "A spiral tower of stacked keycaps punching up through the clouds. "
            "Every floor sits higher than the last and all of the stairs are "
            "just a little bit of a reach."
        ),
        "hero_name": "the Typist",
        "npc_name": "Archivist Yui",
        "boss_name": "The Q-Bit",
        "tone": (
            "Breathless mountaineering nerd. Obsessed with altitude, reaching "
            "up and coming home, and how thin the air is on the number row."
        ),
        "dialogue": {
            "intro": [
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "Floor: {stage}. The wind up here tastes faintly of static."},
                    {"portrait": "npc", "speaker": "Archivist Yui",
                     "text": "Reach for {keys}. Up and back, then home again. This tower only respects round trips."},
                ],
                [
                    {"portrait": "npc", "speaker": "Archivist Yui",
                     "text": "Climbers who reach and forget to come home get stranded on the top row forever. We feed them. It is sad."},
                    {"portrait": "hero", "speaker": "the Typist",
                     "text": "Understood. Up, then back."},
                ],
                [
                    {"portrait": "npc", "speaker": "Archivist Yui",
                     "text": "{keys} live one floor above your knuckles. Stretch, strike, return. Do not, under any circumstance, stand up."},
                ],
            ],
            "outro": [
                [
                    {"portrait": "npc", "speaker": "Archivist Yui",
                     "text": "Altitude gained. Your fingers went up and, crucially, came back down."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "Another floor is stamped into the climb ledger. The clouds are below you now, showing off."},
                ],
                [
                    {"portrait": "npc", "speaker": "Archivist Yui",
                     "text": "Excellent reach. The tower has made a note of your knuckles."},
                ],
            ],
            "boss_intro": [
                [
                    {"portrait": "boss", "speaker": "The Q-Bit",
                     "text": "I sit in the corner no finger wants to visit. Pinky, upper left, thin air. Come and get me, climber."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "The top of the tower is exactly one key wide."},
                    {"portrait": "boss", "speaker": "The Q-Bit",
                     "text": "Everyone drills the rest of the row. Nobody practices me."},
                ],
                [
                    {"portrait": "boss", "speaker": "The Q-Bit",
                     "text": "A Q without its U is a bluff, and U is very far away. Reach anyway, Typist."},
                    {"portrait": "hero", "speaker": "the Typist",
                     "text": "I brought both hands. I will manage."},
                ],
            ],
            "boss_win": [
                [
                    {"portrait": "boss", "speaker": "The Q-Bit",
                     "text": "Impossible. My corner was unreachable. It said so in the brochure."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "The Q-Bit pops like a bubble of cold air. The stairs keep going down, which is new."},
                    {"portrait": "npc", "speaker": "Archivist Yui",
                     "text": "Down? Nobody has ever gone down. Do be careful."},
                ],
                [
                    {"portrait": "boss", "speaker": "The Q-Bit",
                     "text": "Fine. Take the summit. Mind the hole in the floor; the bottom row is awake."},
                ],
            ],
            "boss_lose": [
                [
                    {"portrait": "boss", "speaker": "The Q-Bit",
                     "text": "Back down you go. Gravity is undefeated, and so am I."},
                ],
                [
                    {"portrait": "npc", "speaker": "Archivist Yui",
                     "text": "You reached too far and lost your anchor. Home row first, always, then up."},
                ],
                [
                    {"portrait": "boss", "speaker": "The Q-Bit",
                     "text": "The corner remains mine. Stretch that pinky and try again."},
                ],
            ],
        },
        "boss_lines": [
            "The air is thin. So is your reach.",
            "My corner remains unvisited.",
            "Reach higher. No, higher.",
            "You came home far too slowly.",
            "Nobody practices me. It shows.",
            "Up, strike, home. You skipped one.",
            "Gravity sends its regards.",
            "One key wide and you still missed.",
        ],
    },
    3: {
        "setting": (
            "Damp caverns beneath the board where the bottom row was exiled for "
            "being inconvenient. Everything down here is lit by the soft green "
            "glow of a very old status bar."
        ),
        "hero_name": "the Typist",
        "npc_name": "Vim the Exile",
        "boss_name": "Z-Wraith",
        "tone": (
            "Gloomy cavern-dwelling exile with a grudge and surprisingly good "
            "jokes. Talks about being forgotten and about curling fingers down."
        ),
        "dialogue": {
            "intro": [
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "The floor of the keyboard opens. Something below is typing back."},
                    {"portrait": "npc", "speaker": "Vim the Exile",
                     "text": "{keys}? Nobody comes down here for {keys}. Welcome anyway. Curl your fingers and mind the gap."},
                ],
                [
                    {"portrait": "npc", "speaker": "Vim the Exile",
                     "text": "Up there they call us the bottom row. Down here we call it the foundation. Now reach down without looking."},
                ],
                [
                    {"portrait": "npc", "speaker": "Vim the Exile",
                     "text": "Rule one of the Undergrid: the wrist does not move. Only the fingers go spelunking."},
                    {"portrait": "hero", "speaker": "the Typist",
                     "text": "Rule two?"},
                    {"portrait": "npc", "speaker": "Vim the Exile",
                     "text": "There is no rule two. Rule one is quite enough."},
                ],
            ],
            "outro": [
                [
                    {"portrait": "npc", "speaker": "Vim the Exile",
                     "text": "You went down and came back. Most visitors just pretend this row does not exist."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "The cavern hums approvingly. Somewhere far below, a forgotten key is finally pressed."},
                ],
                [
                    {"portrait": "npc", "speaker": "Vim the Exile",
                     "text": "Not bad, surface-dweller. The gap has been thoroughly minded."},
                ],
            ],
            "boss_intro": [
                [
                    {"portrait": "boss", "speaker": "Z-Wraith",
                     "text": "Zzzz. I slept eleven years. Nobody typed me. Nobody needed me. And now you arrive with that little pinky."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "Something long and cold unfolds from the lower left corner."},
                    {"portrait": "boss", "speaker": "Z-Wraith",
                     "text": "I am the least-used letter and by far the most patient one."},
                ],
                [
                    {"portrait": "boss", "speaker": "Z-Wraith",
                     "text": "Undo. Redo. Undo. I have watched you press me by accident a thousand times. Now do it on purpose."},
                ],
            ],
            "boss_win": [
                [
                    {"portrait": "boss", "speaker": "Z-Wraith",
                     "text": "Struck on purpose. Deliberately. With intent. I have not felt that in years. Thank you."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "The Z-Wraith dissolves into a lowercase sigh and drifts off to sleep."},
                    {"portrait": "npc", "speaker": "Vim the Exile",
                     "text": "Let it rest. It earned the nap."},
                ],
                [
                    {"portrait": "boss", "speaker": "Z-Wraith",
                     "text": "Go up. The Citadel is loud, and it insists on using both hands."},
                ],
            ],
            "boss_lose": [
                [
                    {"portrait": "boss", "speaker": "Z-Wraith",
                     "text": "Back to the surface, pretender. The bottom row keeps its secrets."},
                ],
                [
                    {"portrait": "npc", "speaker": "Vim the Exile",
                     "text": "You lifted your wrist. The Undergrid always notices. Down, not out."},
                ],
                [
                    {"portrait": "boss", "speaker": "Z-Wraith",
                     "text": "Zzzz. Wake me when you can actually reach."},
                ],
            ],
        },
        "boss_lines": [
            "Zzzz. Was that an attempt?",
            "Your wrist moved. Cheater.",
            "Down here we count your misses.",
            "Curl the fingers. Do not lunge.",
            "The bottom row remembers.",
            "Eleven years asleep, still faster.",
            "Mind the gap, surface-dweller.",
            "Accidents do not count as hits.",
        ],
    },
    4: {
        "setting": (
            "A granite fortress where every stone is a capital letter. The "
            "gates open only when both hands agree: one to hold, one to strike."
        ),
        "hero_name": "the Typist",
        "npc_name": "Caps Lock",
        "boss_name": "Lord Shift",
        "tone": (
            "Pompous, shouty, and obsessed with cooperation between the hands. "
            "Caps Lock is a sad over-eager bureaucrat who was demoted."
        ),
        "dialogue": {
            "intro": [
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "The Citadel gate is carved with a single word, in capitals, and it is rude."},
                    {"portrait": "npc", "speaker": "Caps Lock",
                     "text": "I ruled here once. One lever, all caps, no nuance. Now: hold with one hand, strike {keys} with the other."},
                ],
                [
                    {"portrait": "npc", "speaker": "Caps Lock",
                     "text": "Two hands. TWO. One holds the gate, one walks through it. No, you may not use me. I am on leave."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "Stone letters grind into place, every one of them shouting."},
                    {"portrait": "npc", "speaker": "Caps Lock",
                     "text": "Capitals are teamwork, Typist. Shift is a handshake, not a hammer."},
                ],
            ],
            "outro": [
                [
                    {"portrait": "npc", "speaker": "Caps Lock",
                     "text": "Both hands cooperated. Disgusting. Effective. Well done."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "The gate opens without shouting, which in this fortress counts as a miracle."},
                ],
                [
                    {"portrait": "npc", "speaker": "Caps Lock",
                     "text": "Look at you, shifting properly. I have not been this jealous since the nineties."},
                ],
            ],
            "boss_intro": [
                [
                    {"portrait": "boss", "speaker": "Lord Shift",
                     "text": "I do nothing alone, Typist, and that is my power. Press me by myself and watch the world stay exactly the same."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "A vast key descends, wider than any other, and waits to be held."},
                    {"portrait": "boss", "speaker": "Lord Shift",
                     "text": "Hold me. Commit. Half a press is a whole failure."},
                ],
                [
                    {"portrait": "boss", "speaker": "Lord Shift",
                     "text": "Your left hand and your right hand have never once been introduced. Embarrassing. Let us fix that with violence."},
                ],
            ],
            "boss_win": [
                [
                    {"portrait": "boss", "speaker": "Lord Shift",
                     "text": "You held and struck in one breath. Rise, Typist. And do stop shouting, it is unbecoming."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "Lord Shift kneels, which takes both hands. The capitals soften back into ordinary stone."},
                    {"portrait": "npc", "speaker": "Caps Lock",
                     "text": "May I have my lever back? No? Understood."},
                ],
                [
                    {"portrait": "boss", "speaker": "Lord Shift",
                     "text": "Proper capitals at last. Go to the harbor; the punctuation there does not play fair."},
                ],
            ],
            "boss_lose": [
                [
                    {"portrait": "boss", "speaker": "Lord Shift",
                     "text": "You released too early. A capital half-made is just a loud mistake."},
                ],
                [
                    {"portrait": "npc", "speaker": "Caps Lock",
                     "text": "You tried to do it all with one hand. I respect that. It does not work."},
                ],
                [
                    {"portrait": "boss", "speaker": "Lord Shift",
                     "text": "Again. Hold, strike, release. In that order, Typist."},
                ],
            ],
        },
        "boss_lines": [
            "One hand cannot hold the world.",
            "You released me far too early.",
            "Louder is not the same as bigger.",
            "Both hands, Typist. BOTH.",
            "A capital half-made, as usual.",
            "Hold. Strike. In that order.",
            "Your left hand is asleep.",
            "Teamwork. Look it up.",
        ],
    },
    5: {
        "setting": (
            "A crooked port town at the edge of the map where punctuation and "
            "numbers are unloaded from ships in crates. Nothing here is a "
            "letter and everything here has opinions."
        ),
        "hero_name": "the Typist",
        "npc_name": "Harbormaster Ampersand",
        "boss_name": "The Null Pointer",
        "tone": (
            "Salty dockside trader banter. Jokes about shipping manifests, "
            "paired brackets, and figures that stubbornly refuse to add up."
        ),
        "dialogue": {
            "intro": [
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "Gulls circle the harbor, screeching in what is unmistakably a comma."},
                    {"portrait": "npc", "speaker": "Harbormaster Ampersand",
                     "text": "Fresh crate in: {keys}. Handle with the pinky and handle gently, they bruise."},
                ],
                [
                    {"portrait": "npc", "speaker": "Harbormaster Ampersand",
                     "text": "Numbers and marks, Typist. The row nobody practices and everybody needs. Sign here. Twice."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "Dock ledger, page {stage}. The ink is still wet and slightly salty."},
                    {"portrait": "npc", "speaker": "Harbormaster Ampersand",
                     "text": "Out at the edge of the map we trade in {keys}. Mind the reach; home row is a long walk from here."},
                ],
            ],
            "outro": [
                [
                    {"portrait": "npc", "speaker": "Harbormaster Ampersand",
                     "text": "Manifest matches. That almost never happens. Take a coin."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "The crates are stacked, the brackets are paired, and the harbor is briefly at peace."},
                ],
                [
                    {"portrait": "npc", "speaker": "Harbormaster Ampersand",
                     "text": "Clean paperwork, Typist. Punctuation respects you now, which is worse than it sounds."},
                ],
            ],
            "boss_intro": [
                [
                    {"portrait": "boss", "speaker": "The Null Pointer",
                     "text": "I am what remains when you reach for something that is not there. Reach carefully."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "The sea flattens. The horizon narrows into a single blinking caret."},
                    {"portrait": "boss", "speaker": "The Null Pointer",
                     "text": "Nothing at this address. Nothing at any address. Type into the void, Typist."},
                ],
                [
                    {"portrait": "boss", "speaker": "The Null Pointer",
                     "text": "You memorized letters. Numbers. Marks. Now handle the one key that points at absolutely nothing."},
                ],
            ],
            "boss_win": [
                [
                    {"portrait": "boss", "speaker": "The Null Pointer",
                     "text": "You dereferenced me. Impossible. There was nothing here to hit."},
                ],
                [
                    {"portrait": "narrator", "speaker": "",
                     "text": "The Null Pointer collapses into a tidy little zero and rolls quietly into the sea."},
                    {"portrait": "npc", "speaker": "Harbormaster Ampersand",
                     "text": "Log it as resolved. Nobody will believe us."},
                ],
                [
                    {"portrait": "boss", "speaker": "The Null Pointer",
                     "text": "The map ends here and you do not. Well typed, Typist."},
                ],
            ],
            "boss_lose": [
                [
                    {"portrait": "boss", "speaker": "The Null Pointer",
                     "text": "Segmentation of the spirit. Try again, if you still exist."},
                ],
                [
                    {"portrait": "npc", "speaker": "Harbormaster Ampersand",
                     "text": "It got you on the reach. Slow down, aim, then commit."},
                ],
                [
                    {"portrait": "boss", "speaker": "The Null Pointer",
                     "text": "Nothing happened. Nothing ever happens. Again."},
                ],
            ],
        },
        "boss_lines": [
            "You aimed at nothing and missed.",
            "Address invalid. Try again.",
            "The reach is long and you are short.",
            "Nothing here. Nothing there either.",
            "Your manifest does not balance.",
            "Numbers punish the impatient.",
            "Zero. That is your damage. Zero.",
            "The map ends. So does your combo.",
        ],
    },
}


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def _stable_hash(*parts) -> int:
    """Hash that survives process restarts, unlike hash() on strings."""
    raw = "|".join(str(p) for p in parts).encode("utf-8", "replace")
    return int.from_bytes(hashlib.md5(raw).digest()[:8], "big")


def _attr(obj, name: str, default=""):
    """Defensive getattr: Agent 1's Stage/World classes are still in flight."""
    try:
        value = getattr(obj, name, default)
    except Exception:
        return default
    return default if value is None else value


def _lore(world_id) -> dict:
    try:
        entry = WORLD_LORE.get(int(world_id))
    except (TypeError, ValueError):
        entry = None
    return entry or WORLD_LORE[1]


def _ascii(text) -> str:
    """Plain printable ASCII, single-spaced, no control characters."""
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2014", "-").replace("\u2013", "-").replace("\u2026", "...")
    text = "".join(ch for ch in text if 32 <= ord(ch) <= 126)
    return re.sub(r"\s+", " ", text).strip()


def pretty_keys(keys: str) -> str:
    """'fj' -> 'F and J', 'ru' -> 'R and U', ';' -> 'SEMICOLON'."""
    chars = [c for c in _ascii(keys) if c != " "]
    if not chars:
        return "these keys"
    names = [_KEY_NAMES.get(c, c.upper()) for c in dict.fromkeys(chars)]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _fill(text: str, values: dict) -> str:
    """Substitute {name} placeholders without exploding on stray braces."""
    return re.sub(
        r"\{(\w+)\}",
        lambda m: str(values.get(m.group(1), m.group(0))),
        text,
    )


def _clip(text: str, limit: int) -> str:
    """Truncate on a word boundary when possible."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    if space >= limit - 24 and space > 0:
        cut = cut[:space]
    return cut.rstrip(" ,;:-").strip()


# --------------------------------------------------------------------------
# Dialogue
# --------------------------------------------------------------------------


def fallback_dialogue(world_id: int, stage, kind: str) -> list[dict]:
    """Hand-written dialogue for a world/stage/kind. Never raises."""
    try:
        return _fallback_dialogue(world_id, stage, kind)
    except Exception:
        return [
            {
                "speaker": "",
                "portrait": "narrator",
                "text": "The quest continues. Fingers home, eyes up.",
            }
        ]


def _fallback_dialogue(world_id: int, stage, kind: str) -> list[dict]:
    lore = _lore(world_id)
    kind = kind if kind in DIALOGUE_KINDS else "intro"

    variants = lore["dialogue"].get(kind) or lore["dialogue"]["intro"]
    stage_id = _attr(stage, "id", 0)
    new_keys = str(_attr(stage, "new_keys", ""))
    stage_title = _ascii(str(_attr(stage, "title", ""))) or "Training"

    variant = variants[_stable_hash(world_id, stage_id, kind) % len(variants)]
    values = {
        "keys": pretty_keys(new_keys),
        "stage": stage_title,
        "hero": lore["hero_name"],
        "npc": lore["npc_name"],
        "boss": lore["boss_name"],
        "world": lore.get("title", ""),
    }

    lines = []
    for entry in variant[:3]:
        portrait = entry.get("portrait", "narrator")
        if portrait not in PORTRAITS:
            portrait = "narrator"
        speaker = entry.get("speaker") or _default_speaker(lore, portrait)
        text = _clip(_ascii(_fill(entry.get("text", ""), values)), MAX_DIALOGUE_CHARS)
        if not text:
            continue
        lines.append({"speaker": _ascii(speaker)[:40], "portrait": portrait, "text": text})
    return lines


def _default_speaker(lore: dict, portrait: str) -> str:
    if portrait == "hero":
        return lore["hero_name"]
    if portrait == "npc":
        return lore["npc_name"]
    if portrait == "boss":
        return lore["boss_name"]
    return ""


def fallback_boss_line(world_id: int, context: dict) -> str:
    """A short taunt. Varies between calls even for identical context."""
    try:
        lore = _lore(world_id)
        taunts = lore.get("boss_lines") or ["..."]
        ctx = context if isinstance(context, dict) else {}
        seed = _stable_hash(
            world_id,
            ctx.get("hp"),
            ctx.get("boss_hp"),
            ctx.get("combo"),
            next(_salt),
        )
        return _clip(_ascii(taunts[seed % len(taunts)]), MAX_BOSS_LINE_CHARS) or "..."
    except Exception:
        return "..."


# --------------------------------------------------------------------------
# Offline line generator
# --------------------------------------------------------------------------

_wordlist_cache: list[str] | None = None


def load_wordlist() -> list[str]:
    """Read data/wordlist.txt once. Returns [] if the file is missing."""
    global _wordlist_cache
    if _wordlist_cache is None:
        words = []
        try:
            with WORDLIST_PATH.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    word = raw.strip().lower()
                    if word and word.isalpha() and word.isascii():
                        words.append(word)
        except Exception:
            words = []
        _wordlist_cache = words
    return _wordlist_cache


def _hand(char: str) -> str:
    low = char.lower()
    if low in _LEFT_KEYS:
        return "left"
    if low in _RIGHT_KEYS:
        return "right"
    return "either"


def _flatten_keys(keys, allowed: set) -> list[str]:
    """weak_keys arrives as a list of strings; new_keys as one string."""
    out = []
    if isinstance(keys, str):
        items = [keys]
    elif isinstance(keys, (list, tuple, set)):
        items = list(keys)
    else:
        items = []
    for item in items:
        for char in str(item):
            if char in allowed and char != " " and char not in out:
                out.append(char)
    return out


def fallback_lines(allowed_keys: str, new_keys: str, mode: str,
                   weak_keys: list, count: int) -> list[str]:
    """Offline drill/word generator.

    Deterministic for a given set of inputs apart from a rotating salt, and
    structurally incapable of emitting a character outside `allowed_keys`
    (a space is always permitted).
    """
    try:
        count = max(1, int(count))
    except (TypeError, ValueError):
        count = 1
    try:
        lines = _fallback_lines(allowed_keys or "", new_keys or "", mode or "drill",
                               weak_keys or [], count)
    except Exception:
        lines = []

    # Last-resort guarantee: exactly `count` non-empty, in-alphabet lines.
    allowed = set(allowed_keys or "") | {" "}
    safe = []
    for line in lines:
        line = line.rstrip()
        if line and all(ch in allowed for ch in line) and len(line) <= 90:
            safe.append(line)
    while len(safe) < count:
        safe.append(_emergency_line(allowed_keys or "", len(safe)))
    return safe[:count]


def _emergency_line(allowed_keys: str, index: int) -> str:
    chars = [c for c in dict.fromkeys(allowed_keys) if c != " "]
    if not chars:
        return " "
    pattern = chars * 4
    start = index % len(chars)
    seq = pattern[start:start + 6] or chars
    chunk = "".join(seq)
    line = " ".join([chunk] * max(1, LINE_MIN_CHARS // max(1, len(chunk) + 1)))
    return line[:LINE_MAX_CHARS].rstrip()


def _fallback_lines(allowed_keys: str, new_keys: str, mode: str,
                    weak_keys: list, count: int) -> list[str]:
    allowed = set(allowed_keys) | {" "}
    usable = [c for c in dict.fromkeys(allowed_keys) if c != " "]
    if not usable:
        return []

    new = _flatten_keys(new_keys, allowed) or usable[-2:]
    weak = [c for c in _flatten_keys(weak_keys, allowed) if c not in new]

    seed = _stable_hash(allowed_keys, new_keys, mode, "".join(weak), count, next(_salt))
    rng = random.Random(seed)

    mode = (mode or "drill").lower()
    if mode in ("words", "sentences", "boss"):
        pool = _word_pool(allowed)
        if len(pool) >= 12:
            return _word_lines(rng, pool, new, weak, mode, allowed, count)

    return _cluster_lines(rng, usable, new, weak, count)


def _word_pool(allowed: set) -> list[str]:
    letters = {c.lower() for c in allowed if c.isalpha()}
    if not letters:
        return []
    return [w for w in load_wordlist() if 2 <= len(w) <= 10 and set(w) <= letters]


# Sprinkled into "sentences" mode so lines read like English instead of soup.
_FUNCTION_WORDS = (
    "the", "a", "and", "to", "of", "in", "is", "it", "that", "was", "for", "on",
    "with", "as", "at", "his", "her", "you", "they", "not", "but", "all", "can",
    "had", "one", "out", "up", "so", "if", "or", "we", "do", "see", "who", "get",
    "go", "like", "from", "this", "then", "than", "when", "what", "are", "be",
    "by", "an", "my", "no", "him", "she", "he", "its", "our", "there", "into",
)


def _word_lines(rng, pool, new, weak, mode, allowed, count) -> list[str]:
    """Assemble 30-55 character lines, biased toward new and weak keys."""
    new_set = {c.lower() for c in new}
    weak_set = {c.lower() for c in weak}

    weights = []
    for word in pool:
        chars = set(word)
        weight = 1.0
        if chars & new_set:
            weight += 4.0
        if chars & weak_set:
            weight += 2.5
        if 3 <= len(word) <= 8:
            weight += 1.0
        if mode == "boss" and len(word) <= 6:
            weight += 0.75
        weights.append(weight)

    upper_ok = {c for c in allowed if c.isupper()}
    period = "." if "." in allowed else ""
    comma = "," if "," in allowed else ""
    bang = "!" if "!" in allowed else ""

    letters = {c.lower() for c in allowed if c.isalpha()}
    funcs = [w for w in _FUNCTION_WORDS if set(w) <= letters] if mode == "sentences" else []

    # A wordlist can never teach digits or punctuation, so when those are the
    # keys of the hour we mint tokens for them: "shall 4907" / "glass, dash."
    focus = list(dict.fromkeys(list(new) + list(weak)))
    digit_keys = [c for c in focus if c.isdigit()]
    digit_pool = digit_keys * 3 + [c for c in allowed if c.isdigit()]
    punct_keys = [c for c in focus if not c.isalnum() and c != " "]

    lines = []
    guard = 0
    while len(lines) < count and guard < count * 40:
        guard += 1
        target = rng.randint(LINE_MIN_CHARS + 4, LINE_MAX_CHARS)
        if mode == "boss":
            target = rng.randint(LINE_MIN_CHARS, LINE_MAX_CHARS - 8)
        tail = ""
        if mode == "sentences" and period:
            tail = period
        elif mode == "boss" and bang:
            tail = bang

        words = []
        length = 0
        picks = 0
        last_was_glue = False
        while length < target and picks < 24:
            picks += 1
            if digit_pool and rng.random() < 0.32:
                word = "".join(rng.choice(digit_pool) for _ in range(rng.randint(2, 4)))
                last_was_glue = False
            elif funcs and words and not last_was_glue and rng.random() < 0.4:
                word = rng.choice(funcs)
                last_was_glue = True
            else:
                word = rng.choices(pool, weights=weights, k=1)[0]
                word = _maybe_capitalize(rng, word, upper_ok, new)
                last_was_glue = False
            if words and word == words[-1]:
                continue
            extra = len(word) + (1 if words else 0)
            if length + extra + len(tail) > LINE_MAX_CHARS:
                if length >= LINE_MIN_CHARS - 6:
                    break
                continue
            words.append(word)
            length += extra

        if not words:
            continue
        for mark in _punct_marks(rng, punct_keys, comma, mode, len(words)):
            spot = rng.randint(0, len(words) - 2) if len(words) > 1 else 0
            if length + 1 + len(tail) <= LINE_MAX_CHARS and not words[spot][-1:].isdigit():
                words[spot] = words[spot] + mark
                length += 1

        line = " ".join(words) + tail
        if len(line) < 12 or line in lines:
            continue
        lines.append(line)

    if len(lines) < count:
        usable = [c for c in dict.fromkeys("".join(sorted(allowed))) if c != " "]
        lines.extend(_cluster_lines(rng, usable, new, weak, count - len(lines)))
    return lines[:count]


def _punct_marks(rng, punct_keys, comma, mode, word_count) -> list[str]:
    """Which punctuation marks to hang off the ends of words in this line."""
    if word_count < 3:
        return []
    if punct_keys:
        return [rng.choice(punct_keys) for _ in range(rng.randint(1, 2))]
    if mode == "sentences" and comma and word_count >= 5 and rng.random() < 0.45:
        return [comma]
    return []


_CLUSTER_PATTERNS = (
    "xyx", "yxy", "xxy", "yyx", "xyxy", "xyyx", "xxyy", "yxxy", "xyy", "yxx",
    "xxx", "yyy", "xyxx", "yxyy",
)


def _cluster_lines(rng, usable, new, weak, count) -> list[str]:
    """Rhythmic finger-drill clusters, alternating hands where possible."""
    if not usable:
        return []

    # Heavily weight the stage's new keys, then weak keys, then everything else.
    bag = []
    for char in new:
        bag.extend([char] * 6)
    for char in weak:
        bag.extend([char] * 3)
    for char in usable:
        bag.append(char)
    if not bag:
        bag = list(usable)

    lines = []
    guard = 0
    while len(lines) < count and guard < count * 40:
        guard += 1
        target = rng.randint(LINE_MIN_CHARS + 2, LINE_MAX_CHARS)
        clusters = []
        length = 0
        while length < target:
            cluster = _make_cluster(rng, bag)
            extra = len(cluster) + (1 if clusters else 0)
            if length + extra > LINE_MAX_CHARS:
                break
            clusters.append(cluster)
            length += extra
            if len(clusters) > 20:
                break
        if not clusters:
            clusters = [_make_cluster(rng, bag)]
        line = " ".join(clusters)
        if len(line) < 8 or line in lines:
            if guard < count * 20:
                continue
        lines.append(line)
    return lines[:count]


def _make_cluster(rng, bag) -> str:
    x = rng.choice(bag)
    # Prefer a partner on the other hand so drills alternate left/right.
    others = [c for c in bag if c != x]
    opposite = [c for c in others if _hand(c) != _hand(x)]
    if opposite and rng.random() < 0.72:
        y = rng.choice(opposite)
    elif others:
        y = rng.choice(others)
    else:
        y = x
    pattern = rng.choice(_CLUSTER_PATTERNS)
    return pattern.replace("x", x).replace("y", y)


def _maybe_capitalize(rng, word, upper_ok, new) -> str:
    """Shift stages unlock capitals; use them when they are actually allowed."""
    if not word or not upper_ok:
        return word
    head = word[0].upper()
    if head not in upper_ok:
        return word
    chance = 0.55 if head in set(new) else 0.2
    if rng.random() < chance:
        return head + word[1:]
    return word

"""Groq-backed text generation for KEYSTROKE QUEST, with a hard offline floor.

Contract: nothing in this module may ever raise. Every public function catches
everything, validates whatever the model said, and falls back to `story.py`.
The game is fully playable with no API key and no internet connection.

Model notes (openai/gpt-oss-20b):
  * strict structured outputs are supported via
    response_format={"type": "json_schema", "json_schema": {...}}
  * strict mode requires every object to list all properties in `required`
    and to set "additionalProperties": false, or the API returns 400
  * streaming is incompatible with structured outputs, so we never stream
  * on any failure we retry once with {"type": "json_object"} and a prompt that
    spells the shape out in words, then give up and generate offline
"""

from __future__ import annotations

import json
import re

import config
import story

MAX_LINE_CHARS = 90
PORTRAITS = story.PORTRAITS
DIALOGUE_KINDS = story.DIALOGUE_KINDS


# --------------------------------------------------------------------------
# Availability
# --------------------------------------------------------------------------


def is_ai_enabled() -> bool:
    """True only when a key is configured and the groq SDK imports cleanly."""
    try:
        return bool(config.ai_enabled())
    except Exception:
        return False


def _attr(obj, name: str, default=""):
    """getattr that also survives objects with an exploding __getattr__.

    Agent 1 is writing the World/Stage classes concurrently, so nothing here
    assumes anything about them beyond the contract.
    """
    try:
        value = getattr(obj, name, default)
    except Exception:
        return default
    return default if value is None else value


# --------------------------------------------------------------------------
# Groq plumbing
# --------------------------------------------------------------------------


def _complete(messages: list, response_format: dict, temperature: float) -> str:
    from groq import Groq

    client = Groq(
        api_key=config.GROQ_API_KEY,
        timeout=float(getattr(config, "AI_TIMEOUT_SECONDS", 12) or 12),
    )
    resp = client.chat.completions.create(
        messages=messages,
        model=config.GROQ_MODEL,
        response_format=response_format,
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""


def _ask_json(messages: list, schema_name: str, schema: dict,
              shape_hint: str, temperature: float = 0.9):
    """Strict json_schema first, then one json_object retry. None on failure."""
    strict = {
        "type": "json_schema",
        "json_schema": {"name": schema_name, "schema": schema, "strict": True},
    }
    try:
        return _parse_object(_complete(messages, strict, temperature))
    except Exception:
        pass

    try:
        retry = list(messages) + [
            {
                "role": "system",
                "content": (
                    "Reply with JSON only, no prose and no markdown fences. "
                    "Use exactly this JSON shape: " + shape_hint
                ),
            }
        ]
        return _parse_object(_complete(retry, {"type": "json_object"}, temperature))
    except Exception:
        return None


def _parse_object(raw: str):
    """Parse a JSON object, tolerating fences or chatter around it."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except Exception:
            return None
    return data if isinstance(data, dict) else None


# --------------------------------------------------------------------------
# generate_lines
# --------------------------------------------------------------------------

_LINES_SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {"type": "string"},
        }
    },
    "required": ["lines"],
    "additionalProperties": False,
}

_MODE_BRIEF = {
    "drill": (
        "Write rhythmic finger-drill clusters, not words. Example shape: "
        "'fjf jfj fff jjj fjfj'. Groups of two to four characters separated by "
        "single spaces, alternating hands where the allowed keys permit it."
    ),
    "words": (
        "Write real lowercase English words separated by single spaces. No "
        "invented words, no abbreviations, nothing that needs a letter you were "
        "not given."
    ),
    "sentences": (
        "Write short natural English sentences that still obey the character "
        "restriction. They may read a little oddly, but every word must be a "
        "real word."
    ),
    "boss": (
        "Write punchy combat-flavored phrases a 16-bit RPG hero would shout "
        "mid-fight: short, rhythmic, aggressive, all real words."
    ),
}


def generate_lines(*, allowed_keys: str, new_keys: str, mode: str,
                   weak_keys: list, count: int) -> dict:
    """Typing lines for one stage. Always returns exactly `count` safe lines."""
    try:
        count = max(1, int(count))
    except (TypeError, ValueError):
        count = 1
    allowed_keys = allowed_keys if isinstance(allowed_keys, str) else ""
    new_keys = new_keys if isinstance(new_keys, str) else ""
    mode = (mode or "drill").lower()
    weak = _weak_list(weak_keys)

    lines = []
    if is_ai_enabled():
        try:
            data = _ask_json(
                _lines_messages(allowed_keys, new_keys, mode, weak, count),
                "drill",
                _LINES_SCHEMA,
                '{"lines": ["line one", "line two"]}',
                temperature=1.0,
            )
            if data is not None:
                lines = _sanitize_lines(data.get("lines"), allowed_keys, count)
        except Exception:
            lines = []

    source = "groq" if lines else "fallback"
    _top_up(lines, allowed_keys, new_keys, mode, weak, count)
    return {"lines": lines[:count], "source": source}


def _lines_messages(allowed_keys: str, new_keys: str, mode: str,
                    weak: list, count: int) -> list:
    shown = allowed_keys.replace(" ", "")
    brief = _MODE_BRIEF.get(mode, _MODE_BRIEF["drill"])
    weak_note = (
        "The player is currently weakest on these keys, so use them often: "
        + " ".join(weak)
        if weak
        else "The player has no measured weak keys yet."
    )
    user = (
        f"Generate {count} typing practice lines for a retro typing game.\n\n"
        f"ALLOWED CHARACTERS (this is an absolute hard limit): {shown} and the space character.\n"
        "Any line containing a character outside that set is discarded, so do not "
        "use any other letter, digit, or punctuation mark.\n"
        f"KEYS BEING TAUGHT THIS STAGE (weight these very heavily): {new_keys or shown}\n"
        f"{weak_note}\n\n"
        f"STYLE: {brief}\n\n"
        "RULES:\n"
        f"- exactly {count} lines\n"
        "- each line is 30 to 55 characters long, so it takes 20-45 seconds to type a stage\n"
        "- single spaces only, never two in a row, no leading or trailing space\n"
        "- no newlines inside a line, no quotes around lines, plain ASCII only\n"
        "- lines must differ from each other\n"
    )
    return [
        {
            "role": "system",
            "content": (
                "You are a typing-curriculum generator for a retro pixel-art "
                "typing game. You obey character restrictions with absolute "
                "precision; a single stray character ruins the drill. You reply "
                "with JSON only."
            ),
        },
        {"role": "user", "content": user},
    ]


def _weak_list(weak_keys) -> list:
    out = []
    if isinstance(weak_keys, str):
        weak_keys = [weak_keys]
    if isinstance(weak_keys, (list, tuple, set)):
        for item in weak_keys:
            if isinstance(item, dict):
                item = item.get("key", "")
            for char in str(item or ""):
                if char.strip() and char not in out:
                    out.append(char)
    return out


def _sanitize_lines(raw, allowed_keys: str, limit: int) -> list:
    """Drop anything that leaks a character outside allowed_keys (+ space).

    This is the whole point of the module: the model is not trusted at all.
    """
    allowed = set(allowed_keys or "") | {" "}
    lower_only = not any(ch.isupper() for ch in (allowed_keys or ""))

    out = []
    if not isinstance(raw, (list, tuple)):
        return out
    for item in raw:
        if isinstance(item, (list, tuple)):
            item = " ".join(str(part) for part in item)
        if not isinstance(item, str):
            continue
        line = item.replace("\t", " ").replace("\r", " ").replace("\n", " ")
        line = re.sub(r"\s+", " ", line).strip()
        if lower_only:
            line = line.lower()
        if not line or len(line) > MAX_LINE_CHARS:
            continue
        if any(ch not in allowed for ch in line):
            continue
        if line in out:
            continue
        out.append(line)
        if len(out) >= limit:
            break
    return out


def _top_up(lines: list, allowed_keys: str, new_keys: str, mode: str,
            weak: list, count: int) -> None:
    """Pad `lines` in place from the offline generator until it holds `count`."""
    for _ in range(8):
        if len(lines) >= count:
            return
        try:
            extra = story.fallback_lines(allowed_keys, new_keys, mode, weak, count)
        except Exception:
            extra = []
        for line in _sanitize_lines(extra, allowed_keys, count * 4):
            if line not in lines:
                lines.append(line)
                if len(lines) >= count:
                    return

    # Duplicates are acceptable; a short stage is not.
    index = 0
    while len(lines) < count:
        try:
            filler = story.fallback_lines(allowed_keys, new_keys, mode, weak, 1)
        except Exception:
            filler = []
        safe = _sanitize_lines(filler, allowed_keys, 1)
        lines.append(safe[0] if safe else (lines[index % len(lines)] if lines else " "))
        index += 1


# --------------------------------------------------------------------------
# generate_dialogue
# --------------------------------------------------------------------------

_DIALOGUE_SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string"},
                    "portrait": {"type": "string", "enum": list(PORTRAITS)},
                    "text": {"type": "string"},
                },
                "required": ["speaker", "portrait", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["lines"],
    "additionalProperties": False,
}

_KIND_BRIEF = {
    "intro": "The scene just before training begins. Set up the stage and the new keys.",
    "outro": "A short victory beat right after the player clears the stage.",
    "boss_intro": "The boss appears and taunts the Typist before the fight.",
    "boss_win": "The boss has just been defeated. Let it lose with style.",
    "boss_lose": "The Typist lost. Sting, but stay encouraging enough to retry.",
}


def generate_dialogue(*, world, stage, kind: str, context: dict) -> dict:
    """1-3 lines of in-character dialogue. Never raises."""
    kind = kind if kind in DIALOGUE_KINDS else "intro"
    world_id = _world_id(world)
    lore = story.WORLD_LORE.get(world_id, story.WORLD_LORE[1])

    if is_ai_enabled():
        try:
            data = _ask_json(
                _dialogue_messages(world, stage, kind, context, lore),
                "dialogue",
                _DIALOGUE_SCHEMA,
                '{"lines": [{"speaker": "Name", "portrait": "npc", "text": "One sentence."}]}',
                temperature=1.0,
            )
            if data is not None:
                lines = _sanitize_dialogue(data.get("lines"), lore)
                if lines:
                    return {"lines": lines, "source": "groq"}
        except Exception:
            pass

    return {"lines": story.fallback_dialogue(world_id, stage, kind), "source": "fallback"}


def _dialogue_messages(world, stage, kind: str, context: dict, lore: dict) -> list:
    new_keys = str(_attr(stage, "new_keys", ""))
    stage_title = str(_attr(stage, "title", "")) or "Training"
    is_boss = bool(_attr(stage, "is_boss", False))
    world_title = str(_attr(world, "title", "")) or lore.get("title", "")
    boss_name = str(_attr(world, "boss_name", "")) or lore["boss_name"]
    theme = str(_attr(world, "theme", ""))
    world_lore_text = str(_attr(world, "lore", ""))
    ctx = context if isinstance(context, dict) else {}
    weak = _weak_list(ctx.get("weak_keys"))

    system = (
        "You write dialogue for KEYSTROKE QUEST, a 16-bit pixel-art typing RPG. "
        "Voice: SNES-era JRPG script. Terse, vivid, funny in a dry way, never "
        "winking at the player. Plain ASCII only: no emoji, no markdown, no "
        "smart quotes, no stage directions in asterisks.\n\n"
        f"WORLD: {world_title}\n"
        f"SETTING: {lore['setting']}\n"
        f"TONE: {lore['tone']}\n"
        f"HERO (portrait 'hero'): {lore['hero_name']}\n"
        f"GUIDE NPC (portrait 'npc'): {lore['npc_name']}\n"
        f"BOSS (portrait 'boss'): {boss_name}\n"
        "Unattributed scene text uses portrait 'narrator' with an empty speaker."
    )
    user = (
        f"SCENE: {_KIND_BRIEF[kind]}\n"
        f"STAGE: {stage_title}{' (BOSS STAGE)' if is_boss else ''}\n"
        f"KEYS TAUGHT THIS STAGE: {story.pretty_keys(new_keys) if new_keys else 'review of everything so far'}\n"
        f"CSS THEME HINT: {theme}\n"
        f"EXTRA WORLD LORE: {world_lore_text}\n"
        f"PLAYER'S WEAK KEYS: {' '.join(weak) if weak else 'none measured yet'}\n\n"
        "Reference the keys being taught in-world rather than as keyboard "
        "trivia. For example, the Home Row Dojo talks about anchoring on the F "
        "and J bumps; Skyreach Tower talks about reaching up a floor.\n\n"
        "RULES:\n"
        "- 1 to 3 lines total\n"
        "- every line under 140 characters\n"
        "- portrait is one of: hero, npc, boss, narrator\n"
        "- speaker is the character's name, or an empty string for narrator\n"
        "- plain ASCII, no emoji, no markdown, no asterisks\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _sanitize_dialogue(raw, lore: dict) -> list:
    if not isinstance(raw, (list, tuple)):
        return []
    out = []
    for item in raw:
        if isinstance(item, str):
            item = {"text": item}
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            continue
        text = story._ascii(item["text"]).replace("*", "").strip()
        text = story._clip(text, story.MAX_DIALOGUE_CHARS)
        if len(text) < 2:
            continue
        portrait = str(item.get("portrait", "") or "").strip().lower()
        if portrait not in PORTRAITS:
            portrait = "narrator"
        speaker = story._ascii(item.get("speaker", ""))[:40]
        if portrait != "narrator" and not speaker:
            speaker = story._default_speaker(lore, portrait)
        if portrait == "narrator":
            speaker = ""
        out.append({"speaker": speaker, "portrait": portrait, "text": text})
        if len(out) >= 3:
            break
    return out


# --------------------------------------------------------------------------
# generate_boss_line
# --------------------------------------------------------------------------

_BOSS_LINE_SCHEMA = {
    "type": "object",
    "properties": {"line": {"type": "string"}},
    "required": ["line"],
    "additionalProperties": False,
}


def generate_boss_line(*, world, context: dict) -> dict:
    """A single mid-fight taunt under 80 characters. Never raises."""
    world_id = _world_id(world)
    ctx = context if isinstance(context, dict) else {}

    if is_ai_enabled():
        try:
            lore = story.WORLD_LORE.get(world_id, story.WORLD_LORE[1])
            data = _ask_json(
                _boss_line_messages(world, ctx, lore),
                "boss_line",
                _BOSS_LINE_SCHEMA,
                '{"line": "One short taunt."}',
                temperature=1.1,
            )
            raw = data.get("line") if data is not None else None
            if isinstance(raw, str):
                line = story._ascii(raw).replace("*", "").strip()
                line = story._clip(line, story.MAX_BOSS_LINE_CHARS)
                if len(line) >= 2:
                    return {"line": line, "source": "groq"}
        except Exception:
            pass

    return {"line": story.fallback_boss_line(world_id, ctx), "source": "fallback"}


def _boss_line_messages(world, ctx: dict, lore: dict) -> list:
    boss_name = str(_attr(world, "boss_name", "")) or lore["boss_name"]
    system = (
        f"You are {boss_name}, a boss in a 16-bit pixel-art typing RPG.\n"
        f"SETTING: {lore['setting']}\n"
        f"TONE: {lore['tone']}\n"
        "You taunt the Typist mid-battle in one short line. Plain ASCII only, "
        "no emoji, no markdown, no asterisks. Reply with JSON only."
    )
    user = (
        "Write one taunt, under 80 characters, aimed at the player's typing.\n"
        f"YOUR REMAINING HP: {ctx.get('boss_hp', 'unknown')}\n"
        f"PLAYER HP: {ctx.get('hp', 'unknown')}\n"
        f"PLAYER COMBO: {ctx.get('combo', 'unknown')}\n"
        f"PLAYER WPM: {ctx.get('wpm', 'unknown')}\n"
        f"PLAYER ACCURACY: {ctx.get('accuracy', 'unknown')}\n"
        f"RECENT MISSED KEYS: {' '.join(_weak_list(ctx.get('weak_keys'))) or 'none'}\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _world_id(world) -> int:
    try:
        wid = int(_attr(world, "id", 1) or 1)
    except (TypeError, ValueError):
        wid = 1
    return wid if wid in story.WORLD_LORE else 1

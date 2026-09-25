"""Scoring, ranking and levelling rules for KEYSTROKE QUEST.

Accuracy is a 0.0-1.0 float everywhere.  This module is deliberately
dependency-free (it must never import ``db``) so ``db`` can import it.
"""

# XP needed to climb out of level n is ``XP_PER_LEVEL * n``, so each level costs
# more than the last.
XP_PER_LEVEL = 100

# rank_for blend weights.
_ACC_WEIGHT = 0.65
_SPEED_WEIGHT = 0.30
_COMBO_WEIGHT = 0.05
_RANK_BANDS = [("S", 0.95), ("A", 0.87), ("B", 0.78), ("C", 0.68)]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _goal_wpm(stage) -> float:
    return float(getattr(stage, "goal_wpm", 10) or 10)


def _goal_accuracy(stage) -> float:
    return float(getattr(stage, "goal_accuracy", 0.95) or 0.95)


def passed(stage, wpm: float, accuracy: float) -> bool:
    """A stage is cleared only when both goals are met."""
    return float(accuracy) >= _goal_accuracy(stage) and float(wpm) >= _goal_wpm(stage)


def stars_for(stage, wpm: float, accuracy: float) -> int:
    """0 stars for a failed run, otherwise 1-3."""
    if not passed(stage, wpm, accuracy):
        return 0
    accuracy = float(accuracy)
    stars = 1
    if accuracy >= 0.97:
        stars = 2
    if accuracy >= 0.99 and float(wpm) >= _goal_wpm(stage) * 1.25:
        stars = 3
    return stars


def rank_for(stage, wpm: float, accuracy: float, combo_max: int) -> str:
    """Blended letter grade: accuracy dominates, speed matters, combo nudges."""
    accuracy = _clamp(float(accuracy))
    speed = _clamp(float(wpm) / (_goal_wpm(stage) * 1.25))
    combo = _clamp(int(combo_max or 0) / 100.0)
    score = accuracy * _ACC_WEIGHT + speed * _SPEED_WEIGHT + combo * _COMBO_WEIGHT
    for rank, floor in _RANK_BANDS:
        if score >= floor:
            return rank
    return "D"


def xp_for_run(stage, wpm, accuracy, combo_max, hp_left) -> int:
    """XP for one attempt.  Even a wipe pays out a little."""
    wpm = max(0.0, float(wpm or 0))
    accuracy = _clamp(float(accuracy or 0))
    combo_max = max(0, int(combo_max or 0))
    hp_left = max(0, int(hp_left or 0))

    xp = 0.0
    if passed(stage, wpm, accuracy):
        xp += 50
    xp += wpm * 1.5                          # speed bonus
    xp += max(0.0, accuracy - 0.80) * 250    # up to +50 for clean typing
    xp += (combo_max // 10) * 5              # combo bonus
    xp += hp_left * 10                       # survival bonus
    if getattr(stage, "is_boss", False):
        xp *= 2
    return max(5, int(xp))


def level_for_xp(xp: int) -> dict:
    """Walk the level table so levels get progressively more expensive."""
    try:
        remaining = max(0, int(xp or 0))
    except (TypeError, ValueError):
        remaining = 0

    level = 1
    while True:
        cost = XP_PER_LEVEL * level
        if remaining < cost:
            break
        remaining -= cost
        level += 1

    xp_for_next = XP_PER_LEVEL * level
    return {
        "level": level,
        "xp_into_level": int(remaining),
        "xp_for_next": int(xp_for_next),
        "progress": round(remaining / xp_for_next, 4) if xp_for_next else 0.0,
    }

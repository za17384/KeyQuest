# KEYSTROKE QUEST

A retro pixel-art typing RPG. You learn touch typing one finger at a time, and
the game generates your practice text and story dialogue with AI so the drills
target the keys *you* personally keep missing.

## Play

```
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000

## Turning on the AI (optional)

The game is fully playable without this. With a key, the drills and the story
dialogue are freshly written each time and aimed at your weak keys.

1. Go to https://console.groq.com/keys and sign in (free).
2. Click **Create API Key** and copy the `gsk_...` value.
3. Rename `.env.example` to `.env`.
4. Paste the key after `GROQ_API_KEY=` and save.
5. Restart `python app.py`.

The title screen shows `AI: ONLINE` when the key is working.

## How it teaches

Five worlds, thirty stages, following the key order used by established touch
typing courses:

| World | Keys taught | Boss |
| --- | --- | --- |
| The Home Row Dojo | `fj dk sl a; gh` | Sensei Semicolon |
| Skyreach Tower | `ru ei wo qp ty` | The Q-Bit |
| The Undergrid | `vm c, x. z/ bn` | Z-Wraith |
| Shift Citadel | capitals | Lord Shift |
| Glyph Harbor | punctuation and numbers | The Null Pointer |

Every stage shows a keyboard and a pair of hands that highlight the exact finger
for the next key. Typos cost hearts, correct keystrokes build a combo, and boss
stages drain the boss's HP bar as you type. Each keystroke is recorded, so the
PLAYER CARD screen can show you a per-key accuracy heatmap and generate drills
aimed at your five worst keys.

## Controls

| Key | Action |
| --- | --- |
| Space / Enter | Advance story dialogue |
| Tab then Enter | Restart the stage |
| Escape | Back to the world map |
| Backspace | Fix the current word |

## Project layout

```
app.py          Flask routes and JSON API
config.py       env vars, Groq key and model
curriculum.py   worlds, stages, finger map
db.py           SQLite: runs, key stats, progress, cache
progress.py     XP, levels, ranks, star ratings
ai.py           Groq client, prompts, output validation
story.py        world lore and offline fallback writing
static/js/      typing engine, keyboard, game loop, dialogue, chiptune audio
static/css/     the 16-bit theme
templates/      title, map, stage, results, stats
```

Progress is stored in `keystroke_quest.db` next to the app. Delete that file to
start a fresh save.

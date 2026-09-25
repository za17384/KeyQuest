"""KEYSTROKE QUEST - a retro pixel typing RPG.

Run with:  python app.py   then open http://127.0.0.1:5000
"""

import json

from flask import Flask, jsonify, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

import ai
import config
import curriculum
import db
import progress as progress_mod

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

db.init_db()


def public_origin() -> str:
    if config.PUBLIC_URL:
        return config.PUBLIC_URL
    return request.url_root.rstrip("/")


def public_url(path: str = "/") -> str:
    origin = public_origin()
    if not path or path == "/":
        return origin + "/"
    if not path.startswith("/"):
        path = "/" + path
    return origin + path


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------


@app.route("/")
def title_screen():
    player = db.get_player()
    prog = db.get_progress()
    return render_template(
        "title.html",
        player=player,
        level=progress_mod.level_for_xp(player["xp"]),
        has_save=prog["unlocked_max"] > 1,
        ai_on=ai.is_ai_enabled(),
    )


@app.route("/map")
def world_map():
    prog = db.get_progress()
    player = db.get_player()
    worlds = []
    for world in curriculum.WORLDS:
        stages = [curriculum.stage_dict(curriculum.get_stage(sid)) for sid in world.stage_ids]
        for stage in stages:
            state = prog["stages"].get(stage["id"], {})
            stage["passed"] = bool(state.get("passed"))
            stage["stars"] = int(state.get("stars") or 0)
            stage["best_wpm"] = state.get("best_wpm") or 0
            stage["locked"] = stage["id"] > prog["unlocked_max"]
        entry = curriculum.world_dict(world)
        entry["stages"] = stages
        entry["locked"] = all(s["locked"] for s in stages)
        worlds.append(entry)
    return render_template(
        "map.html",
        worlds=worlds,
        player=player,
        level=progress_mod.level_for_xp(player["xp"]),
    )


@app.route("/stage/<int:stage_id>")
def stage_screen(stage_id):
    stage = curriculum.get_stage(stage_id)
    if stage is None:
        return redirect(url_for("world_map"))
    prog = db.get_progress()
    if stage_id > prog["unlocked_max"]:
        return redirect(url_for("world_map"))
    world = curriculum.get_world(stage.world_id)
    return render_template(
        "stage.html",
        stage=curriculum.stage_dict(stage),
        world=curriculum.world_dict(world),
        stage_id=stage_id,
        player=db.get_player(),
    )


@app.route("/stats")
def stats_screen():
    player = db.get_player()
    return render_template(
        "stats.html",
        player=player,
        level=progress_mod.level_for_xp(player["xp"]),
    )


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------


@app.route("/api/stage/<int:stage_id>")
def api_stage(stage_id):
    stage = curriculum.get_stage(stage_id)
    if stage is None:
        return jsonify({"error": "no such stage"}), 404
    world = curriculum.get_world(stage.world_id)

    weak = [w["key"] for w in db.get_weak_keys(5) if w["key"] in stage.allowed_keys]
    cache_key = f"stage:{stage_id}:{''.join(sorted(weak))}"

    cached = None if request.args.get("fresh") else db.cache_get(cache_key)
    if cached:
        payload = cached
    else:
        text = ai.generate_lines(
            allowed_keys=stage.allowed_keys,
            new_keys=stage.new_keys,
            mode=stage.mode,
            weak_keys=weak,
            count=config.LINES_PER_STAGE,
        )
        intro = ai.generate_dialogue(
            world=world,
            stage=stage,
            kind="boss_intro" if stage.is_boss else "intro",
            context={"weak_keys": weak},
        )
        outro = ai.generate_dialogue(
            world=world,
            stage=stage,
            kind="boss_win" if stage.is_boss else "outro",
            context={},
        )
        payload = {
            "lines": text["lines"],
            "dialogue": {"intro": intro["lines"], "outro": outro["lines"]},
            "source": text["source"],
        }
        db.cache_set(cache_key, payload)

    return jsonify(
        {
            "stage": curriculum.stage_dict(stage),
            "world": curriculum.world_dict(world),
            "lines": payload["lines"],
            "dialogue": payload["dialogue"],
            "source": payload.get("source", "fallback"),
            "weak_keys": weak,
            "finger_map": curriculum.FINGER_MAP,
        }
    )


@app.route("/api/session", methods=["POST"])
def api_session():
    data = request.get_json(silent=True) or {}
    stage = curriculum.get_stage(int(data.get("stage_id", 0)))
    if stage is None:
        return jsonify({"error": "no such stage"}), 404

    wpm = float(data.get("wpm") or 0)
    raw_wpm = float(data.get("raw_wpm") or wpm)
    accuracy = float(data.get("accuracy") or 0)
    duration_ms = int(data.get("duration_ms") or 0)
    combo_max = int(data.get("combo_max") or 0)
    hp_left = int(data.get("hp_left") or 0)
    keystrokes = data.get("keystrokes") or []

    did_pass = progress_mod.passed(stage, wpm, accuracy)
    stars = progress_mod.stars_for(stage, wpm, accuracy)
    rank = progress_mod.rank_for(stage, wpm, accuracy, combo_max)
    xp = progress_mod.xp_for_run(stage, wpm, accuracy, combo_max, hp_left)

    db.upsert_keystats(keystrokes)
    db.record_run(stage.id, wpm, raw_wpm, accuracy, duration_ms, combo_max, hp_left, xp)
    if did_pass:
        db.mark_passed(stage.id, wpm, accuracy, stars)
    player = db.add_xp(xp)

    return jsonify(
        {
            "passed": did_pass,
            "stars": stars,
            "rank": rank,
            "xp_gained": xp,
            "player": {**player, **progress_mod.level_for_xp(player["xp"])},
            "next_stage_id": curriculum.next_stage_id(stage.id) if did_pass else None,
            "unlocked": did_pass,
        }
    )


@app.route("/api/progress")
def api_progress():
    player = db.get_player()
    return jsonify(
        {
            "player": {**player, **progress_mod.level_for_xp(player["xp"])},
            "progress": db.get_progress(),
            "weak_keys": db.get_weak_keys(5),
        }
    )


@app.route("/api/boss-line", methods=["POST"])
def api_boss_line():
    data = request.get_json(silent=True) or {}
    stage = curriculum.get_stage(int(data.get("stage_id", 0)))
    if stage is None:
        return jsonify({"line": "..."}), 404
    world = curriculum.get_world(stage.world_id)
    return jsonify(ai.generate_boss_line(world=world, context=data.get("context") or {}))


@app.route("/api/stats")
def api_stats():
    heatmap = db.get_key_heatmap()
    fingers = {}
    for row in heatmap:
        agg = fingers.setdefault(
            (row["hand"], row["finger"]),
            {"hand": row["hand"], "finger": row["finger"], "correct": 0, "miss": 0},
        )
        agg["correct"] += row.get("correct", 0)
        agg["miss"] += row.get("miss", 0)
    finger_rows = []
    for agg in fingers.values():
        total = agg["correct"] + agg["miss"]
        agg["accuracy"] = agg["correct"] / total if total else 0.0
        finger_rows.append(agg)

    return jsonify(
        {
            "heatmap": heatmap,
            "weak_keys": db.get_weak_keys(5),
            "history": db.get_wpm_history(50),
            "fingers": finger_rows,
        }
    )


@app.route("/api/settings", methods=["POST"])
def api_settings():
    db.save_settings(request.get_json(silent=True) or {})
    return jsonify({"ok": True})


@app.route("/robots.txt")
def robots_txt():
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        f"Sitemap: {public_url('/sitemap.xml')}\n"
    )
    return body, 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/sitemap.xml")
def sitemap_xml():
    pages = [
        (public_url("/"), "1.0", "daily"),
        (public_url("/map"), "0.8", "weekly"),
        (public_url("/stats"), "0.3", "monthly"),
    ]
    urls = []
    for loc, priority, changefreq in pages:
        urls.append(
            "<url>"
            f"<loc>{loc}</loc>"
            f"<changefreq>{changefreq}</changefreq>"
            f"<priority>{priority}</priority>"
            "</url>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(urls)
        + "</urlset>"
    )
    return xml, 200, {"Content-Type": "application/xml; charset=utf-8"}


@app.context_processor
def inject_globals():
    settings = db.get_player().get("settings", {})
    origin = public_origin()
    path = request.path if request.path != "/" else "/"
    jsonld = {
        "@context": "https://schema.org",
        "@type": "VideoGame",
        "name": config.SITE_NAME,
        "alternateName": "KEYSTROKE QUEST",
        "description": config.DEFAULT_DESCRIPTION,
        "url": public_url("/"),
        "image": origin + url_for("static", filename="img/og.png"),
        "genre": ["Typing", "Educational", "Role-playing"],
        "gamePlatform": "Web browser",
        "applicationCategory": "Game",
        "operatingSystem": "Any",
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
    }
    return {
        "kq_settings": settings,
        "kq_settings_json": json.dumps(settings),
        "kq_ai_on": ai.is_ai_enabled(),
        "kq_site_name": config.SITE_NAME,
        "kq_description": config.DEFAULT_DESCRIPTION,
        "kq_canonical": public_url(path),
        "kq_og_image": origin + url_for("static", filename="img/og.png"),
        "kq_jsonld": json.dumps(jsonld),
    }


if __name__ == "__main__":
    app.run(debug=True, port=5000)

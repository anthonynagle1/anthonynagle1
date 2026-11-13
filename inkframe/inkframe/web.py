"""Phone-friendly web page for uploading pictures and changing settings."""

from __future__ import annotations

import logging
import threading
from datetime import datetime

from flask import Flask, abort, flash, redirect, render_template, request, send_file, url_for

from .config import clean_settings

log = logging.getLogger(__name__)


def create_app(frame) -> Flask:
    app = Flask(__name__)
    app.secret_key = "inkframe-local"  # only used for flash messages on your home network
    app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

    @app.before_request
    def _activity():
        frame.touch()

    @app.get("/")
    def index():
        alarm = frame.next_alarm()
        return render_template(
            "index.html",
            ids=list(reversed(frame.library.ids())),
            current=frame.state.get("current_id"),
            s=frame.settings.data,
            battery=frame.power.battery(),
            plugged=frame.power.plugged_in(),
            has_battery=frame.power.available(),
            busy=frame.busy,
            next_alarm=alarm.strftime("%a %-I:%M %p") if alarm else "—",
            awake_left=max(0, int(frame.settings["awake_minutes"] - frame.idle_seconds() / 60)),
        )

    @app.post("/upload")
    def upload():
        was_empty = not frame.library.ids()
        added, failed = [], 0
        for f in request.files.getlist("photos"):
            if not f or not f.filename:
                continue
            try:
                added.append(frame.library.add(f.stream, frame.settings))
            except Exception:
                log.exception("Could not read %s", f.filename)
                failed += 1
        if added:
            flash(f"Added {len(added)} picture{'s' * (len(added) != 1)}.")
            if was_empty:
                frame.show_async(added[0])
        if failed:
            flash(f"{failed} file(s) couldn't be read as pictures.")
        return redirect(url_for("index"))

    @app.post("/show/<image_id>")
    def show(image_id):
        if not frame.library.exists(image_id):
            abort(404)
        frame.show_async(image_id)
        flash("Updating the screen — takes about 30 seconds.")
        return redirect(url_for("index"))

    @app.post("/next")
    def next_picture():
        frame.show_async()
        flash("Showing the next picture — takes about 30 seconds.")
        return redirect(url_for("index"))

    @app.post("/delete/<image_id>")
    def delete(image_id):
        frame.library.delete(image_id)
        flash("Picture deleted.")
        return redirect(url_for("index"))

    @app.post("/settings")
    def settings():
        try:
            values = clean_settings(request.form.to_dict())
        except (ValueError, TypeError):
            flash("Some settings weren't valid, so nothing was changed.")
            return redirect(url_for("index"))
        needs_reprep = any(values.get(k) != frame.settings.get(k) for k in ("fit", "background") if k in values)
        needs_redraw = any(values.get(k) != frame.settings.get(k) for k in ("rotation", "saturation") if k in values)
        frame.settings.update(**values)
        frame.schedule_next(datetime.now())
        if needs_reprep:
            frame.reprepare_async()
        elif needs_redraw and frame.library.exists(frame.state.get("current_id")):
            frame.show_async(frame.state.get("current_id"))
        flash("Settings saved.")
        return redirect(url_for("index"))

    @app.post("/sleep")
    def sleep():
        flash("Going to sleep. Press the PiSugar button to wake it again.")
        threading.Timer(2.0, frame.sleep).start()
        return redirect(url_for("index"))

    @app.get("/thumb/<image_id>")
    def thumb(image_id):
        path = frame.library.thumbs / f"{image_id}.jpg"
        if not path.exists():
            abort(404)
        return send_file(path, max_age=86400)

    return app

"""The frame controller: ties together pictures, the display and power."""

from __future__ import annotations

import logging
import socket
import threading
import time
from datetime import datetime, timedelta

from PIL import Image

from . import imaging, power
from .config import load_settings, load_state
from .library import Library

log = logging.getLogger(__name__)

TIMER_WAKE_WINDOW = timedelta(minutes=10)


class Frame:
    def __init__(self, root, display, battery, port: int = 80):
        self.root = root
        self.display = display
        self.power = battery
        self.port = port
        self.settings = load_settings(root)
        self.state = load_state(root)
        self.library = Library(root, display.resolution)
        self._lock = threading.Lock()
        self.busy = ""  # human-readable description of work in progress
        self.last_activity = time.monotonic()

    # --- showing pictures ---------------------------------------------
    def address(self) -> str:
        host = socket.gethostname()
        suffix = "" if self.port == 80 else f":{self.port}"
        return f"http://{host}.local{suffix}"

    def show(self, image_id: str | None = None) -> str | None:
        with self._lock:
            self.busy = "Updating the screen (about 30 seconds)…"
            try:
                return self._show(image_id)
            finally:
                self.busy = ""

    def _show(self, image_id):
        s = self.settings
        if image_id is None:
            image_id = self.library.next_id(self.state, s["order"])
        if image_id is None:
            img = imaging.welcome_screen(self.library.size, self.address())
        else:
            path = self.library.prepared_path(image_id)
            if not path.exists():
                self.library.reprepare_all(s)
            img = Image.open(path).convert("RGB")
            level = self.power.battery()
            if level is not None and level < s["low_battery_percent"] and not self.power.plugged_in():
                img = imaging.add_low_battery(img, level)
        self.display.show(imaging.to_panel(img, s["rotation"]), s["saturation"])
        self.state.update(current_id=image_id, last_shown=datetime.now().isoformat(timespec="seconds"))
        log.info("Showing %s", image_id or "welcome screen")
        return image_id

    def show_async(self, image_id: str | None = None) -> None:
        threading.Thread(target=self.show, args=(image_id,), daemon=True).start()

    def reprepare_async(self) -> None:
        def work():
            with self._lock:
                self.busy = "Re-preparing pictures…"
                try:
                    self.library.reprepare_all(self.settings)
                finally:
                    self.busy = ""
            self.show(self.state.get("current_id") if self.library.exists(self.state.get("current_id")) else None)

        threading.Thread(target=work, daemon=True).start()

    # --- scheduling ----------------------------------------------------
    def next_alarm(self) -> datetime | None:
        value = self.state.get("next_alarm")
        return datetime.fromisoformat(value) if value else None

    def schedule_next(self, now: datetime | None = None) -> datetime:
        s = self.settings
        when = power.next_wake(now or datetime.now(), s["interval_minutes"], s["quiet_start"], s["quiet_end"])
        try:
            self.power.set_alarm(when)
        except OSError:
            log.exception("Failed to set wake alarm")
        self.state.update(next_alarm=when.isoformat(timespec="seconds"))
        return when

    def wake_reason(self, now: datetime | None = None) -> str:
        """'timer' if we were woken by our own alarm, otherwise 'button'."""
        if not self.power.available():
            return "button"
        alarm = self.next_alarm()
        now = now or datetime.now()
        if alarm and abs(now - alarm) <= TIMER_WAKE_WINDOW:
            return "timer"
        return "button"

    def sleep(self) -> None:
        when = self.schedule_next()
        log.info("Sleeping until %s", when)
        if self.power.available():
            power.power_off()
        else:
            log.info("No PiSugar found, so staying on (desk-test mode)")

    def can_sleep(self) -> bool:
        return self.power.available() and not self.power.plugged_in()

    def idle_seconds(self) -> float:
        return time.monotonic() - self.last_activity

    def touch(self) -> None:
        self.last_activity = time.monotonic()

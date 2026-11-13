"""Entry point, run at every boot by systemd.

Timer wake  -> show the next picture, set the next alarm, power off.
Button wake -> start the web page; power off after a few idle minutes
               (stays on while the charger is plugged in).
"""

from __future__ import annotations

import argparse
import logging
import threading
import time
from datetime import datetime

from werkzeug.serving import make_server

from . import power
from .config import data_dir
from .display import get_display
from .frame import Frame
from .web import create_app

log = logging.getLogger("inkframe")


def main() -> None:
    parser = argparse.ArgumentParser(prog="inkframe")
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--preview", action="store_true",
                        help="write preview.png instead of using the screen (for testing)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    root = data_dir()
    battery = power.PiSugar()
    if not battery.available():
        log.warning("PiSugar not found; running without sleep")
        battery = power.NoBattery()
    battery.time_from_rtc()

    frame = Frame(root, get_display(root / "preview.png", args.preview), battery, args.port)

    reason = frame.wake_reason()
    log.info("Woke up: %s", reason)
    if reason == "timer":
        frame.show()
        frame.sleep()
        return

    stay_awake(frame, args.port)


def stay_awake(frame: Frame, port: int) -> None:
    server = make_server("0.0.0.0", port, create_app(frame), threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("Web page at %s", frame.address())

    if not frame.library.ids() or not frame.library.exists(frame.state.get("current_id")):
        frame.show_async()  # welcome screen or first picture
    alarm = frame.next_alarm()
    if not alarm or alarm <= datetime.now():
        frame.schedule_next()

    rtc_saved = False
    while True:
        time.sleep(15)
        if not rtc_saved and power.clock_synced():
            frame.power.rtc_from_pi()  # keep the RTC accurate for future timer wakes
            rtc_saved = True
        alarm = frame.next_alarm()
        if alarm and datetime.now() >= alarm and not frame.busy:
            frame.show()  # time for a new picture while we're awake
            frame.schedule_next()
        if (frame.can_sleep() and not frame.busy
                and frame.idle_seconds() > frame.settings["awake_minutes"] * 60):
            log.info("Idle; going to sleep")
            server.shutdown()
            frame.sleep()
            return


if __name__ == "__main__":
    main()

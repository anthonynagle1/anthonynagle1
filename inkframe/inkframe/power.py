"""PiSugar 3 battery/RTC control and wake scheduling."""

from __future__ import annotations

import logging
import socket
import subprocess
from datetime import datetime, time, timedelta

log = logging.getLogger(__name__)


def _parse_hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def in_quiet_hours(moment: datetime, quiet_start: str, quiet_end: str) -> bool:
    start, end = _parse_hhmm(quiet_start), _parse_hhmm(quiet_end)
    t = moment.time()
    if start == end:
        return False
    if start < end:
        return start <= t < end
    return t >= start or t < end  # spans midnight


def next_wake(now: datetime, interval_minutes: int, quiet_start: str, quiet_end: str) -> datetime:
    """Next refresh time, pushed to the end of quiet hours if needed."""
    wake = (now + timedelta(minutes=interval_minutes)).replace(second=0, microsecond=0)
    if in_quiet_hours(wake, quiet_start, quiet_end):
        end = _parse_hhmm(quiet_end)
        candidate = wake.replace(hour=end.hour, minute=end.minute)
        if candidate <= wake:
            candidate += timedelta(days=1)
        wake = candidate
    return wake


class PiSugar:
    """Talks to pisugar-server over its local TCP API (port 8423)."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8423, timeout: float = 3.0):
        self.host, self.port, self.timeout = host, port, timeout

    def _cmd(self, command: str) -> str:
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.sendall((command + "\n").encode())
            data = s.recv(1024).decode().strip()
        # responses look like "battery: 87.3"
        return data.split(":", 1)[1].strip() if ":" in data else data

    def available(self) -> bool:
        try:
            self._cmd("get model")
            return True
        except OSError:
            return False

    def battery(self) -> float | None:
        try:
            return float(self._cmd("get battery"))
        except (OSError, ValueError):
            return None

    def plugged_in(self) -> bool:
        try:
            return self._cmd("get battery_power_plugged").lower() == "true"
        except OSError:
            return False

    def time_from_rtc(self) -> None:
        """Set the Pi's clock from the PiSugar RTC (the Zero has no clock of its own)."""
        try:
            self._cmd("rtc_rtc2pi")
        except OSError:
            log.warning("Could not read time from PiSugar RTC")

    def rtc_from_pi(self) -> None:
        """Save the Pi's (internet-synced) clock to the RTC."""
        try:
            self._cmd("rtc_pi2rtc")
        except OSError:
            log.warning("Could not write time to PiSugar RTC")

    def set_alarm(self, when: datetime) -> None:
        # 127 = repeat on every weekday; we reset it on every wake anyway.
        stamp = when.astimezone().isoformat(timespec="seconds")
        self._cmd(f"rtc_alarm_set {stamp} 127")
        log.info("Wake alarm set for %s", stamp)


class NoBattery:
    """Used when no PiSugar is found (desk testing): never sleeps."""

    def available(self) -> bool:
        return False

    def battery(self):
        return None

    def plugged_in(self) -> bool:
        return True

    def time_from_rtc(self) -> None: ...
    def rtc_from_pi(self) -> None: ...
    def set_alarm(self, when) -> None: ...


def power_off() -> None:
    subprocess.run(["systemctl", "poweroff"], check=False)


def clock_synced() -> bool:
    try:
        out = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                             capture_output=True, text=True, timeout=5).stdout
        return out.strip() == "yes"
    except (OSError, subprocess.TimeoutExpired):
        return False

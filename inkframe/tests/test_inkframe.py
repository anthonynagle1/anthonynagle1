import io
import random
from datetime import datetime

import pytest
from PIL import Image

from inkframe import imaging
from inkframe.config import clean_settings, load_settings, load_state
from inkframe.display import PreviewDisplay
from inkframe.frame import Frame
from inkframe.library import Library
from inkframe.power import NoBattery, in_quiet_hours, next_wake
from inkframe.web import create_app


def jpeg(size=(4032, 3024), colour="red"):
    buf = io.BytesIO()
    Image.new("RGB", size, colour).save(buf, "JPEG")
    buf.seek(0)
    return buf


# --- imaging ---------------------------------------------------------------
def test_prepare_fill_and_fit_are_exact_portrait_size():
    img = Image.new("RGB", (4000, 3000))
    assert imaging.prepare(img, (1200, 1600), "fill").size == (1200, 1600)
    assert imaging.prepare(img, (1200, 1600), "fit").size == (1200, 1600)


def test_to_panel_rotates_portrait_to_landscape():
    assert imaging.to_panel(Image.new("RGB", (1200, 1600)), 90).size == (1600, 1200)


def test_png_with_transparency_becomes_rgb():
    buf = io.BytesIO()
    Image.new("RGBA", (50, 50), (0, 0, 0, 0)).save(buf, "PNG")
    buf.seek(0)
    assert imaging.open_image(buf).mode == "RGB"


# --- scheduling ------------------------------------------------------------
def test_quiet_hours_across_midnight():
    assert in_quiet_hours(datetime(2026, 1, 1, 23, 0), "22:00", "07:00")
    assert in_quiet_hours(datetime(2026, 1, 1, 6, 59), "22:00", "07:00")
    assert not in_quiet_hours(datetime(2026, 1, 1, 7, 0), "22:00", "07:00")
    assert not in_quiet_hours(datetime(2026, 1, 1, 12, 0), "08:00", "08:00")


def test_next_wake_skips_quiet_hours():
    assert next_wake(datetime(2026, 1, 1, 20, 30), 240, "22:00", "07:00") == datetime(2026, 1, 2, 7, 0)
    assert next_wake(datetime(2026, 1, 1, 9, 15, 42), 240, "22:00", "07:00") == datetime(2026, 1, 1, 13, 15)
    assert next_wake(datetime(2026, 1, 1, 2, 0), 60, "22:00", "07:00") == datetime(2026, 1, 1, 7, 0)


def test_clean_settings_clamps_and_rejects():
    out = clean_settings({"interval_minutes": "1", "saturation": "3", "rotation": "45", "order": "x"})
    assert out == {"interval_minutes": 15, "saturation": 1.0}


# --- library ---------------------------------------------------------------
@pytest.fixture
def lib(tmp_path):
    return Library(tmp_path), load_settings(tmp_path), load_state(tmp_path)


def test_sequential_order_wraps(lib):
    library, settings, state = lib
    ids = [library.add(jpeg(), settings) for _ in range(3)]
    seen = []
    for _ in range(4):
        nxt = library.next_id(state, "sequential")
        state.update(current_id=nxt)
        seen.append(nxt)
    assert seen == ids + ids[:1]


def test_shuffle_shows_every_picture_before_repeating(lib):
    library, settings, state = lib
    ids = {library.add(jpeg(), settings) for _ in range(5)}
    rng = random.Random(1)
    first_round = set()
    for _ in range(5):
        nxt = library.next_id(state, "shuffle", rng)
        state.update(current_id=nxt)
        first_round.add(nxt)
    assert first_round == ids


def test_delete_removes_files(lib):
    library, settings, state = lib
    image_id = library.add(jpeg(), settings)
    library.delete(image_id)
    assert library.ids() == []


# --- frame + web -----------------------------------------------------------
@pytest.fixture
def frame(tmp_path):
    return Frame(tmp_path, PreviewDisplay(tmp_path / "preview.png"), NoBattery(), port=8000)


def test_show_writes_landscape_preview(frame, tmp_path):
    frame.library.add(jpeg((3024, 4032)), frame.settings)
    shown = frame.show()
    assert shown == frame.state["current_id"]
    assert Image.open(tmp_path / "preview.png").size == (1600, 1200)


def test_empty_library_shows_welcome(frame, tmp_path):
    assert frame.show() is None
    assert (tmp_path / "preview.png").exists()


def test_no_battery_is_never_a_timer_wake(frame):
    frame.schedule_next()
    assert frame.wake_reason() == "button"


def test_web_upload_and_pages(frame):
    client = create_app(frame).test_client()
    assert client.get("/").status_code == 200
    r = client.post("/upload", data={"photos": [(jpeg(), "a.jpg"), (io.BytesIO(b"nope"), "b.txt")]},
                    content_type="multipart/form-data", follow_redirects=True)
    assert b"Added 1 picture" in r.data and b"couldn" in r.data
    image_id = frame.library.ids()[0]
    assert client.get(f"/thumb/{image_id}").status_code == 200
    assert client.post("/settings", data={"interval_minutes": "1440", "quiet_start": "23:00",
                                          "quiet_end": "06:30"}).status_code == 302
    assert frame.settings["interval_minutes"] == 1440
    assert client.post(f"/delete/{image_id}").status_code == 302
    assert frame.library.ids() == []

"""Inky Impression driver wrapper, with a file-based stand-in for testing."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

from . import imaging

log = logging.getLogger(__name__)


class InkyDisplay:
    def __init__(self):
        try:
            from inky.auto import auto

            self.inky = auto(ask_user=False, verbose=True)
        except Exception:  # EEPROM not detected; try the 13.3" driver directly
            from inky.inky_el133uf1 import Inky

            self.inky = Inky()
        self.resolution = tuple(self.inky.resolution)
        log.info("Inky display found: %s", self.resolution)

    def show(self, img: Image.Image, saturation: float) -> None:
        try:
            self.inky.set_image(img, saturation=saturation)
        except TypeError:
            self.inky.set_image(img)
        self.inky.show()


class PreviewDisplay:
    """Writes preview.png instead of driving a panel."""

    def __init__(self, path: Path):
        self.path = path
        self.resolution = imaging.PANEL_SIZE

    def show(self, img: Image.Image, saturation: float) -> None:
        img.save(self.path)
        log.info("Preview written to %s", self.path)


def get_display(preview_path: Path, force_preview: bool = False):
    if not force_preview:
        try:
            return InkyDisplay()
        except Exception as exc:  # no hardware / library
            log.warning("No Inky display (%s); using preview file", exc)
    return PreviewDisplay(preview_path)

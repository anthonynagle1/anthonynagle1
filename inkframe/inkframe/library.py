"""Picture storage and playlist order."""

from __future__ import annotations

import random
import time
import uuid
from pathlib import Path

from PIL import Image

from . import imaging

MAX_ORIGINAL = 3000  # px, long edge kept on disk


class Library:
    def __init__(self, root: Path, panel_size=imaging.PANEL_SIZE):
        self.originals = root / "originals"
        self.prepared = root / "prepared"
        self.thumbs = root / "thumbs"
        for d in (self.originals, self.prepared, self.thumbs):
            d.mkdir(parents=True, exist_ok=True)
        self.size = imaging.portrait_size(panel_size)

    # --- storage -------------------------------------------------------
    def ids(self) -> list[str]:
        """Oldest first."""
        files = sorted(self.originals.glob("*.jpg"), key=lambda p: (p.stat().st_mtime, p.name))
        return [p.stem for p in files]

    def add(self, stream, settings) -> str:
        img = imaging.open_image(stream)  # raises if not an image
        img.thumbnail((MAX_ORIGINAL, MAX_ORIGINAL), Image.LANCZOS)
        image_id = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
        img.save(self.originals / f"{image_id}.jpg", quality=92)
        self._prepare(image_id, img, settings)
        return image_id

    def _prepare(self, image_id: str, img: Image.Image, settings) -> None:
        ready = imaging.prepare(img, self.size, settings["fit"], settings["background"])
        ready.save(self.prepared / f"{image_id}.png")
        thumb = ready.copy()
        thumb.thumbnail((300, 400))
        thumb.save(self.thumbs / f"{image_id}.jpg", quality=80)

    def reprepare_all(self, settings) -> None:
        for image_id in self.ids():
            self._prepare(image_id, imaging.open_image(self.originals / f"{image_id}.jpg"), settings)

    def delete(self, image_id: str) -> None:
        for path in (self.originals / f"{image_id}.jpg", self.prepared / f"{image_id}.png",
                     self.thumbs / f"{image_id}.jpg"):
            path.unlink(missing_ok=True)

    def prepared_path(self, image_id: str) -> Path:
        return self.prepared / f"{image_id}.png"

    def exists(self, image_id: str | None) -> bool:
        return bool(image_id) and (self.originals / f"{image_id}.jpg").exists()

    # --- playlist ------------------------------------------------------
    def next_id(self, state, order: str, rng: random.Random | None = None) -> str | None:
        ids = self.ids()
        if not ids:
            return None
        current = state.get("current_id")
        if order == "sequential":
            if current in ids:
                return ids[(ids.index(current) + 1) % len(ids)]
            return ids[0]
        # shuffle: go through every picture once before repeating
        rng = rng or random.Random()
        queue = [i for i in state.get("queue", []) if i in ids]
        if not queue:
            queue = ids[:]
            rng.shuffle(queue)
            if len(queue) > 1 and queue[0] == current:
                queue.append(queue.pop(0))
        choice = queue.pop(0)
        state.update(queue=queue)
        return choice

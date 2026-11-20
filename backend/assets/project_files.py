"""Where a game project keeps its images: <root>/assets/<folder>/ (sprites, backgrounds, ui, fonts), each image
(.png, .gif, .jpg, .jpeg, .webp) beside its .gbsres sidecar. project_images lists them, for the assets RPC or for
anything that counts or walks a project's art."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

from .versions import ASSET_SUFFIXES

# (folder under <root>/assets, the kind the page shows), in listing order.
ASSET_FOLDERS = (("sprites", "sprite"), ("backgrounds", "background"), ("ui", "ui"), ("fonts", "ui"))


def project_images(root: Path, kinds: Iterable[str] | None = None) -> Iterator[tuple[Path, Path, str]]:
    """Each image under root/assets/<folder>/ as (path as found, resolved path, kind), folder by folder in
    ASSET_FOLDERS order and sorted within each; only image suffixes, only regular files, never a link that
    resolves outside root. ``kinds`` keeps only those kinds ("sprite", "background", "ui"). The sidecar of an
    image is ``image.with_name(image.name + ".gbsres")``. A generator: stop early to cap the list."""
    wanted = None if kinds is None else set(kinds)
    # Images resolve to canonical paths, so the containment check needs the canonical root too: a relative root
    # or one through a link would otherwise reject every image. Traversal keeps the root as given.
    try:
        real_root = root.resolve(strict=True)
    except (OSError, RuntimeError):
        return
    for folder, kind in ASSET_FOLDERS:
        if wanted is not None and kind not in wanted:
            continue
        base = root / "assets" / folder
        if not base.is_dir():
            continue
        for image in sorted(base.rglob("*")):
            if image.suffix.lower() not in ASSET_SUFFIXES or not image.is_file():
                continue
            try:
                real = image.resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            if real != real_root and real_root not in real.parents:
                continue
            yield image, real, kind

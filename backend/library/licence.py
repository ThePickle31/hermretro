"""A game's licence: the card's ``license`` and the ``LICENSE`` file hermretro writes from it. Standard library only.

The licences a game may name are the ones below: short enough to write in full, or ones whose text a game may name by
its address (the Creative Commons licences let a work give their URI instead of a copy). A game names none until its
author chooses; publishing waits for one (``release.readiness``: ``NO_LICENSE``).
"""

from __future__ import annotations

import time
from pathlib import Path

LICENSE_FILE = "LICENSE"

_MIT = """MIT License

Copyright (c) {year} {holder}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

_CREATIVE_COMMONS = """{title}
Copyright (c) {year} {holder}

This work is licensed under the Creative Commons {name} License ({short}).
To view a copy of this license, visit {url}
"""

_CC0 = """{title}

To the extent possible under law, {holder} has waived all copyright and related or
neighboring rights to {title}, under the Creative Commons CC0 1.0 Universal Public Domain
Dedication: {url}
"""

_RESERVED = """{title}
Copyright (c) {year} {holder}. All rights reserved.
"""

# The card's ``license`` value -> (the LICENSE text, its fields).
LICENSES = {
    "MIT": (_MIT, {}),
    "CC-BY-4.0": (
        _CREATIVE_COMMONS,
        {
            "name": "Attribution 4.0 International",
            "short": "CC BY 4.0",
            "url": "https://creativecommons.org/licenses/by/4.0/",
        },
    ),
    "CC-BY-SA-4.0": (
        _CREATIVE_COMMONS,
        {
            "name": "Attribution-ShareAlike 4.0 International",
            "short": "CC BY-SA 4.0",
            "url": "https://creativecommons.org/licenses/by-sa/4.0/",
        },
    ),
    "CC-BY-NC-4.0": (
        _CREATIVE_COMMONS,
        {
            "name": "Attribution-NonCommercial 4.0 International",
            "short": "CC BY-NC 4.0",
            "url": "https://creativecommons.org/licenses/by-nc/4.0/",
        },
    ),
    "CC0-1.0": (_CC0, {"url": "https://creativecommons.org/publicdomain/zero/1.0/"}),
    "All-Rights-Reserved": (_RESERVED, {}),
}


def problem(value) -> str | None:
    """Why ``value`` is not a licence a game may name, or None."""
    if value in LICENSES:
        return None
    return "license must be one of: " + ", ".join(LICENSES) + "."


def chosen(card: dict) -> str | None:
    """The licence the card names, or None when it names none (or one that is not allowed)."""
    value = card.get("license")
    return value if value in LICENSES else None


def text(root: Path, card: dict) -> str | None:
    """The ``LICENSE`` file for the card's licence, or None when it names none. The holder is the card's ``author``,
    else the authors of the game; the year is when the game was made."""
    key = chosen(card)
    if key is None:
        return None
    template, fields = LICENSES[key]
    title = (
        card.get("title").strip() if isinstance(card.get("title"), str) and card["title"].strip() else Path(root).name
    )
    author = card.get("author")
    holder = author.strip() if isinstance(author, str) and author.strip() else f"the authors of {title}"
    created = card.get("createdAt")
    year = time.gmtime(created if isinstance(created, (int, float)) and not isinstance(created, bool) else None).tm_year
    return template.format(title=title, holder=holder, year=year, **fields)

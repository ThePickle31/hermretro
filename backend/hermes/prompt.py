"""What the agent reads: the plugin's skills (skills/<name>/SKILL.md) and the ``hermretro.guide`` prompt
section."""

from __future__ import annotations

from pathlib import Path

from . import workflow
from .declare import section, skills

# Not resolved: the same path the plugin was loaded from (a linked install keeps its link).
skills(Path(__file__).parents[2] / "skills")
section("hermretro.guide", workflow.SYSTEM_PROMPT_SECTION, position="after_memory", max_chars=2000)

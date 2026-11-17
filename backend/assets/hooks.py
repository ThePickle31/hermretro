"""Assets' Hermes hooks: keep the version of each game image a reply showed (``post_llm_call``) or a tool looked
at (``post_tool_call``, before build history's snapshot), so a later rewrite does not change what the Build
page shows for an earlier reply."""

from __future__ import annotations

from ..hermes.declare import hook
from . import versions

hook("post_llm_call")(versions.keep_delivered_images)
hook("post_tool_call")(versions.keep_inspected_images)

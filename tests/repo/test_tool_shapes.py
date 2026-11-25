"""The pinned engine tools name each field one way: fields of one name that mean one thing have one shape.

An agent that learns a field from one tool uses it the same way in the next, so every field of every tool's input
schema (at any depth, ``$ref`` resolved) is compared with each other field of the same name and meaning. Two fields
agree when each accepts exactly what the other does: the same JSON types, enum values, number, length and item
ranges, patterns and formats, object keys and required keys, and items that agree. Two forms of one ``anyOf`` are
alternatives, not two uses of a name, so their fields are not compared with each other.

Real differences are listed by path in tests/repo/tool_shape_differences.py, each with why: ``OWN`` fields mean
something of their own and are compared with none of their name, ``GROUPS`` fields share a meaning of their own and
are compared only with each other, and ``NARROWER`` and ``WIDER`` fields are compared with the rest of their meaning
but may accept less, or more, than each of them. A new mismatch is fixed in the engine or listed with its reason; an
entry that is no longer needed fails too. A schema form this check does not compare fails it rather than passing
unread.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from collections import defaultdict
from dataclasses import dataclass, field, replace
from itertools import combinations
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.system.paths import ENGINE_PINS  # noqa: E402 - the repository root goes on sys.path first
from tests.repo.tool_shape_differences import GROUPS, NARROWER, OWN, WIDER  # noqa: E402

# What this check compares; any other keyword fails it, so a new schema form is taught here before it is trusted.
COMPARED = {
    "type",
    "enum",
    "const",
    "minimum",
    "maximum",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "minItems",
    "maxItems",
    "propertyNames",
}
ANNOTATIONS = {"description", "default", "$schema", "title", "examples"}
DEFINITIONS = {"$defs", "definitions"}  # what a $ref points into; read through the $ref
RANGES = (("minimum", "maximum"), ("minLength", "maxLength"), ("minItems", "maxItems"))


class UnsupportedSchema(ValueError):
    pass


@dataclass(frozen=True)
class Allowed:
    own: dict = field(default_factory=dict)
    groups: dict = field(default_factory=dict)
    narrower: dict = field(default_factory=dict)
    wider: dict = field(default_factory=dict)

    def meaning(self, where: str) -> str:
        if where in self.own:
            return where
        return next((why for why, paths in self.groups.items() if where in paths), "")


LISTED = Allowed(OWN, GROUPS, NARROWER, WIDER)


def _merged(node: dict, extra: dict, why: str) -> dict:
    """node with extra's keys added; one key with two different values is a form this check does not compare."""
    clash = sorted(key for key in extra.keys() & node.keys() - ANNOTATIONS if extra[key] != node[key])
    if clash:
        raise UnsupportedSchema(f"{why} sets {clash} again with another value")
    return {**node, **extra}


def resolve(root: dict, node: dict) -> dict:
    """node with its ``$ref`` (a JSON pointer into the same tool's schema) followed and its own keys added."""
    while isinstance(node, dict) and "$ref" in node:
        reference = node["$ref"]
        if not reference.startswith("#"):
            raise UnsupportedSchema(f"$ref {reference!r} points outside the tool's schema")
        target = root
        for part in unquote(reference[1:]).split("/")[1:]:
            part = part.replace("~1", "/").replace("~0", "~")
            target = target[int(part)] if isinstance(target, list) else target[part]
        node = _merged(target, {key: value for key, value in node.items() if key != "$ref"}, f"$ref {reference!r}")
    return node


def branches(root: dict, node: dict) -> list[dict]:
    """The forms node accepts: itself, or each ``anyOf`` option with node's own constraints added."""
    node = resolve(root, node)
    if not isinstance(node, dict):
        raise UnsupportedSchema(f"{json.dumps(node)[:80]} is not a schema object")
    unknown = sorted(node.keys() - COMPARED - ANNOTATIONS - DEFINITIONS - {"anyOf"})
    if unknown:
        raise UnsupportedSchema(f"schema keywords {unknown} are not compared")
    if "anyOf" not in node:
        return [node]
    rest = {key: value for key, value in node.items() if key != "anyOf"}
    return [_merged(branch, rest, "anyOf") for option in node["anyOf"] for branch in branches(root, option)]


def contains(root_a: dict, a: dict, root_b: dict, b: dict) -> bool:
    """Whether field a accepts everything field b does, within the parts of a shape this check compares."""
    return all(any(_holds(root_a, x, root_b, y) for x in branches(root_a, a)) for y in branches(root_b, b))


def equivalent(root_a: dict, a: dict, root_b: dict, b: dict) -> bool:
    return contains(root_a, a, root_b, b) and contains(root_b, b, root_a, a)


def _pattern(node: dict) -> str | None:
    """node's pattern with each plain character class in one order, so [0-9a-f] and [a-f0-9] are one pattern."""
    pattern = node.get("pattern")
    if pattern is None:
        return None
    return re.sub(r"\[([^\]^\\]+)\]", lambda m: "[" + "".join(sorted(re.findall(r".-.|.", m[1]))) + "]", pattern)


def _holds(root_a: dict, a: dict, root_b: dict, b: dict) -> bool:
    if a.get("type") != b.get("type"):
        return False
    values_a = a["enum"] if "enum" in a else [a["const"]] if "const" in a else None
    values_b = b["enum"] if "enum" in b else [b["const"]] if "const" in b else None
    if values_a is not None and (values_b is None or not set(values_b) <= set(values_a)):
        return False
    for low, high in RANGES:
        inf = float("inf")
        if not (a.get(low, -inf) <= b.get(low, -inf) and b.get(high, inf) <= a.get(high, inf)):
            return False
    if _pattern(a) is not None and _pattern(a) != _pattern(b):
        return False
    if "format" in a and a["format"] != b.get("format"):
        return False
    for key in ("items", "propertyNames"):
        if key in a and (key not in b or not contains(root_a, a[key], root_b, b[key])):
            return False
    if a.get("type") == "object" or "properties" in a or "properties" in b:
        return _object_holds(root_a, a, root_b, b)
    return True


def _object_holds(root_a: dict, a: dict, root_b: dict, b: dict) -> bool:
    properties_a, properties_b = a.get("properties", {}), b.get("properties", {})
    extra_a, extra_b = a.get("additionalProperties", True), b.get("additionalProperties", True)
    if not set(a.get("required", ())) <= set(b.get("required", ())):
        return False
    for key, field_b in properties_b.items():
        accepted = (
            contains(root_a, properties_a[key], root_b, field_b)
            if key in properties_a
            else _accepts(root_a, extra_a, root_b, field_b)
        )
        if not accepted:
            return False
    if extra_b is not False and properties_a.keys() - properties_b.keys():
        return False  # b takes any value for a key that a constrains
    return _accepts(root_a, extra_a, root_b, extra_b)


def _accepts(root_a: dict, extra_a, root_b: dict, extra_b) -> bool:
    """Whether a's additionalProperties takes every value b allows there (a schema, or True or False)."""
    if extra_b is False or extra_a is True or extra_a == {}:
        return True
    if extra_a is False or extra_b is True:
        return False
    return contains(root_a, extra_a, root_b, extra_b)


def fields(tools: list[dict]) -> dict[str, list[tuple[str, dict, dict]]]:
    """Every input field of every tool by name: (where, the tool's schema, the field's schema)."""
    found = defaultdict(list)

    def walk(where: str, root: dict, node: dict) -> None:
        forms = branches(root, node)
        for index, branch in enumerate(forms):
            here = f"{where}.anyOf[{index}]" if len(forms) > 1 else where
            if isinstance(branch.get("items"), dict):
                walk(f"{here}[]", root, branch["items"])
            for name, child in (branch.get("properties") or {}).items():
                found[name].append((f"{here}.{name}", root, child))
                walk(f"{here}.{name}", root, child)

    for tool in tools:
        walk(tool["name"], tool["inputSchema"], tool["inputSchema"])
    return found


def alternatives(where_a: str, where_b: str) -> bool:
    """Whether two fields sit in different forms of one anyOf."""
    for part_a, part_b in zip(where_a.split("."), where_b.split("."), strict=False):
        if part_a != part_b:
            return part_a.startswith("anyOf[") and part_b.startswith("anyOf[")
    return False


def agree(allowed: Allowed, a: tuple[str, dict, dict], b: tuple[str, dict, dict]) -> bool:
    (where_a, root_a, node_a), (where_b, root_b, node_b) = a, b
    a_holds_b, b_holds_a = contains(root_a, node_a, root_b, node_b), contains(root_b, node_b, root_a, node_a)
    return (a_holds_b and b_holds_a) or any(
        holds and (where in allowed.wider or other in allowed.narrower)
        for holds, where, other in ((a_holds_b, where_a, where_b), (b_holds_a, where_b, where_a))
    )


def mismatches(tools: list[dict], allowed: Allowed = Allowed()) -> dict[str, list[str]]:
    """Field name: the pairs of its occurrences, of one meaning, that do not agree."""
    found = {}
    for name, occurrences in fields(tools).items():
        pairs = [
            f"{a[0]} / {b[0]}"
            for a, b in combinations(occurrences, 2)
            if allowed.meaning(a[0]) == allowed.meaning(b[0])
            and not alternatives(a[0], b[0])
            and not agree(allowed, a, b)
        ]
        if pairs:
            found[name] = pairs
    return found


def entries(allowed: Allowed):
    """Each listed entry with its paths and the list without it."""
    for kind in ("own", "narrower", "wider"):
        for where in getattr(allowed, kind):
            rest = {key: value for key, value in getattr(allowed, kind).items() if key != where}
            yield f"{kind.upper()} {where}", {where}, replace(allowed, **{kind: rest})
    for why, paths in allowed.groups.items():
        rest = {key: value for key, value in allowed.groups.items() if key != why}
        yield f"GROUPS {why!r}", set(paths), replace(allowed, groups=rest)


def unneeded(tools: list[dict], allowed: Allowed) -> list[str]:
    """The entries whose fields agree without them, or that name no field."""
    stale = []
    for label, paths, without in entries(allowed):
        involved = {
            where for pairs in mismatches(tools, without).values() for pair in pairs for where in pair.split(" / ")
        }
        if not paths & involved:
            stale.append(label)
    return stale


def tool(name: str, field_schema: dict, **root) -> dict:
    return {"name": name, "inputSchema": {"type": "object", "properties": {"f": field_schema}, **root}}


class ToolShapeTests(unittest.TestCase):
    def setUp(self):
        self.tools = json.loads((ENGINE_PINS / "tools.json").read_text())["tools"]

    def test_fields_of_one_name_agree_across_tools(self):
        self.assertEqual(
            mismatches(self.tools, LISTED),
            {},
            "FIX: give these fields one shape in the engine (dist/server.js), or list the differing path in "
            "tests/repo/test_tool_shapes.py (OWN, GROUPS, NARROWER or WIDER) with why it really differs",
        )

    def test_every_listed_difference_is_still_needed(self):
        self.assertEqual(
            unneeded(self.tools, LISTED),
            [],
            "FIX: these fields agree without their entry, or the path is gone; remove the entry",
        )

    def test_equal_shapes_are_required(self):
        narrow = tool("a", {"type": "integer", "minimum": 1, "maximum": 8})
        wide = tool("b", {"type": "integer", "minimum": 1, "maximum": 16})
        overlapping = tool("c", {"type": "integer", "minimum": 4, "maximum": 32})
        self.assertEqual(mismatches([narrow, wide]), {"f": ["a.f / b.f"]})
        self.assertEqual(mismatches([narrow, wide], Allowed(narrower={"a.f": ""})), {})
        self.assertEqual(mismatches([narrow, wide], Allowed(wider={"b.f": ""})), {})
        self.assertEqual(mismatches([narrow, wide], Allowed(narrower={"b.f": ""})), {"f": ["a.f / b.f"]})
        self.assertEqual(mismatches([narrow, overlapping], Allowed(narrower={"a.f": ""})), {"f": ["a.f / c.f"]})
        enum = tool("g", {"type": "string", "enum": ["a", "b"]})
        other_enum = tool("h", {"type": "string", "enum": ["b", "a"]})
        self.assertEqual(mismatches([enum, other_enum]), {})
        self.assertEqual(mismatches([enum, tool("i", {"type": "string", "enum": ["b", "c"]})]), {"f": ["g.f / i.f"]})

    def test_array_bounds_keys_and_required_keys_count(self):
        items = {"type": "array", "items": {"type": "string"}, "maxItems": 4}
        self.assertEqual(mismatches([tool("a", items), tool("b", {**items, "minItems": 1})]), {"f": ["a.f / b.f"]})
        keys = {"type": "object", "properties": {"sceneId": {"type": "string"}}, "additionalProperties": False}
        more_keys = {**keys, "properties": {**keys["properties"], "eventId": {"type": "string"}}}
        self.assertEqual(mismatches([tool("c", keys), tool("d", more_keys)]), {"f": ["c.f / d.f"]})
        self.assertEqual(mismatches([tool("c", keys), tool("d", more_keys)], Allowed(narrower={"c.f": ""})), {})
        required = {**keys, "required": ["sceneId"]}
        self.assertEqual(mismatches([tool("e", keys), tool("g", required)]), {"f": ["e.f / g.f"]})
        open_keys = {key: value for key, value in more_keys.items() if key != "additionalProperties"}
        self.assertEqual(mismatches([tool("c", keys), tool("h", open_keys)], Allowed(narrower={"c.f": ""})), {})
        self.assertEqual(
            mismatches([tool("c", keys), tool("h", open_keys)], Allowed(narrower={"h.f": ""})), {"f": ["c.f / h.f"]}
        )

    def test_a_ref_is_followed_with_its_siblings_and_escapes(self):
        defs = {"$defs": {"a/b": {"type": "integer", "minimum": 0}, "c~d": {"type": "integer", "minimum": 0}}}
        target = {"type": "integer", "minimum": 0, "maximum": 4}
        for pointer in ("#/$defs/a~1b", "#/$defs/c~0d", "#/%24defs/a~1b"):
            with self.subTest(pointer=pointer):
                self.assertEqual(
                    mismatches([tool("a", {"$ref": pointer, "maximum": 4}, **defs), tool("b", target)]), {}
                )
        self.assertEqual(
            mismatches([tool("a", {"$ref": "#/$defs/a~1b"}, **defs), tool("b", target)]), {"f": ["a.f / b.f"]}
        )
        with self.assertRaises(UnsupportedSchema):
            mismatches([tool("a", {"$ref": "#/$defs/a~1b", "minimum": 2}, **defs), tool("b", target)])
        with self.assertRaises(UnsupportedSchema):
            mismatches([tool("a", {"$ref": "other.json#/x"}), tool("b", target)])

    def test_anyof_takes_the_containing_nodes_constraints(self):
        forms = {"anyOf": [{"type": "integer", "minimum": 0}, {"type": "string"}], "maximum": 9}
        spelled = {"anyOf": [{"type": "integer", "minimum": 0, "maximum": 9}, {"type": "string", "maximum": 9}]}
        self.assertEqual(mismatches([tool("a", forms), tool("b", spelled)]), {})
        self.assertEqual(mismatches([tool("a", forms), tool("c", {"anyOf": forms["anyOf"]})]), {"f": ["a.f / c.f"]})
        objects = {"anyOf": [{"type": "object", "properties": {"g": {"type": "string"}}}, {"type": "null"}]}
        other = {"anyOf": [{"type": "object", "properties": {"g": {"type": "integer"}}}, {"type": "null"}]}
        self.assertEqual(
            mismatches([tool("d", objects), tool("e", other)]),
            {"f": ["d.f / e.f"], "g": ["d.f.anyOf[0].g / e.f.anyOf[0].g"]},
        )

    def test_forms_of_one_anyof_are_alternatives(self):
        operation = {
            "type": "array",
            "items": {
                "anyOf": [
                    {"type": "object", "properties": {"type": {"const": "fill", "type": "string"}}},
                    {"type": "object", "properties": {"type": {"const": "place", "type": "string"}}},
                ]
            },
        }
        self.assertEqual(mismatches([tool("a", operation)]), {})
        elsewhere = tool("b", {"type": "object", "properties": {"type": {"type": "string"}}})
        self.assertEqual(
            sorted(mismatches([tool("a", operation), elsewhere])["type"]),
            [
                "a.f[].anyOf[0].type / b.f.type",
                "a.f[].anyOf[1].type / b.f.type",
            ],
        )

    def test_unsupported_forms_are_refused(self):
        for form in (
            {"oneOf": [{"type": "string"}]},
            {"allOf": [{"type": "string"}]},
            {"not": {"type": "string"}},
            {"type": "array", "prefixItems": [{"type": "string"}]},
            {"type": "integer", "exclusiveMaximum": 4},
        ):
            with self.subTest(form=form), self.assertRaises(UnsupportedSchema):
                mismatches([tool("a", form), tool("b", {"type": "string"})])

    def test_one_character_set_in_another_order_is_one_pattern(self):
        hex_a, hex_b = {"type": "string", "pattern": "^[0-9a-f]{64}$"}, {"type": "string", "pattern": "^[a-f0-9]{64}$"}
        self.assertEqual(mismatches([tool("a", hex_a), tool("b", hex_b)]), {})
        upper = {"type": "string", "pattern": "^[A-F0-9]{64}$"}
        self.assertEqual(mismatches([tool("a", hex_a), tool("c", upper)]), {"f": ["a.f / c.f"]})

    def test_meanings_keep_fields_apart(self):
        actor, scene, world = (
            tool(name, {"type": "integer", "minimum": low, "maximum": 255})
            for name, low in (("a", 0), ("b", -9), ("c", -9))
        )
        self.assertEqual(mismatches([actor, scene, world], Allowed(groups={"editor": ["b.f", "c.f"]})), {})
        self.assertEqual(mismatches([actor, scene, world], Allowed(own={"b.f": ""})), {"f": ["a.f / c.f"]})
        stale = unneeded([actor, scene], Allowed(own={"b.f": "", "gone.f": ""}, wider={"a.f": ""}))
        self.assertEqual(stale, ["OWN gone.f", "WIDER a.f"])


if __name__ == "__main__":
    unittest.main()

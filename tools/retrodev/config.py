"""Settings: the repository's policy (tools/retrodev/policy.toml, committed) and personal overrides.

Personal values live in <git common dir>/retrodev/config.toml (never committed, shared by every worktree) and
win over the policy's [config] defaults. Only keys the policy declares can be set, so a typo is refused.

    python tools/retrodev config list | get <key> | set <key> <value> | set <key> ""   (back to the default)
"""

from __future__ import annotations

import copy
import functools
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import repo, state
from .output import Failure, Out

OWN_POLICY = Path(__file__).resolve().with_name("policy.toml")


def load_policy(top: Path) -> dict:
    """The policy of the checkout being worked on (its own rules), else the one beside this code."""
    candidate = top / "tools" / "retrodev" / "policy.toml"
    path = candidate if candidate.is_file() else OWN_POLICY
    return copy.deepcopy(_parse(path.read_text(encoding="utf-8")))


@functools.lru_cache(maxsize=8)
def _parse(text: str) -> dict:
    # Keyed by the text, so an edited policy is read anew (check --watch); every command makes several contexts.
    return tomllib.loads(text)


def local_path(cwd: Path | str) -> Path:
    return state.root(cwd) / "config.toml"


def load_local(cwd: Path | str) -> dict:
    path = local_path(cwd)
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise Failure(f"{path} is not valid TOML ({error})", f"fix or remove {path}")


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    return f'"{escaped}"'


def save_local(cwd: Path | str, values: dict) -> None:
    lines = ["# retrodev personal settings (python tools/retrodev config set <key> <value>); never committed"]
    lines += [f"{key} = {_quote(str(value))}" for key, value in sorted(values.items())]
    state.write_atomic(local_path(cwd), "\n".join(lines) + "\n")


@dataclass
class Context:
    """Everything a command needs: where it runs, the rules, the settings, the gh runner and the output.

    ``fakes`` replaces what tests must never start for real: ``review_run`` (the reviewer's process runner),
    ``review_db`` (the session database the audit reads), ``sleep`` and ``clock`` (CI polling)."""

    cwd: Path
    out: Out
    gh_runner: object = None
    top: Path = Path()
    policy: dict = field(default_factory=dict)
    local: dict = field(default_factory=dict)
    fakes: dict = field(default_factory=dict)
    started: Path = Path()  # where the command was started (kept by at(): a removed worktree may be the shell's)

    @classmethod
    def make(
        cls, cwd: Path | str, out: Out, gh_runner=None, fakes: dict | None = None, started: Path | None = None
    ) -> Context:
        cwd = Path(cwd).resolve()
        top = repo.toplevel(cwd)
        return cls(
            cwd=cwd,
            started=started or cwd,
            out=out,
            gh_runner=gh_runner,
            top=top,
            policy=load_policy(top),
            local=load_local(top),
            fakes=dict(fakes or {}),
        )

    def at(self, path: Path | str) -> Context:
        """The same command's context in another checkout (a worktree, or the main checkout)."""
        return Context.make(path, self.out, gh_runner=self.gh_runner, fakes=self.fakes, started=self.started)

    def get(self, key: str) -> str:
        if key not in self.policy["config"]:
            raise Failure(
                f"'{key}' is not a retrodev setting",
                "use one of: " + ", ".join(sorted(self.policy["config"])),
            )
        value = self.local.get(key)
        return str(value) if value not in (None, "") else str(self.policy["config"][key])

    def source(self, key: str) -> str:
        return "local" if self.local.get(key) not in (None, "") else "policy"

    @property
    def base(self) -> str:
        return self.get("base")

    @property
    def remote(self) -> str:
        return self.get("remote")

    @property
    def remote_base(self) -> str:
        return f"{self.remote}/{self.base}"

    def main(self) -> Path:
        return repo.main_checkout(self.top)

    def worktree_root(self) -> Path:
        main = self.main()
        value = self.get("worktree_root")
        if not value:
            return main.parent / f"{main.name}-wt"
        path = Path(value).expanduser()
        return path if path.is_absolute() else (main.parent / path)

    def command(self, words: list[str]) -> list[str]:
        """A policy command with {python} replaced by the Python running retrodev."""
        return [sys.executable if word == "{python}" else word for word in words]


def run(ctx: Context, action: str, key: str | None, value: str | None) -> int:
    keys = sorted(ctx.policy["config"])
    if action == "list":
        rows = {name: {"value": ctx.get(name), "from": ctx.source(name)} for name in keys}
        for name, row in rows.items():
            ctx.out.say(f"{name} = {row['value']!r}  ({row['from']})")
        ctx.out.set(settings=rows, file=str(local_path(ctx.top)))
        return 0
    if not key:
        raise Failure(f"config {action} needs a key", f"python tools/retrodev config {action} <key>; keys: {keys}")
    current = ctx.get(key)  # refuses unknown keys
    if action == "get":
        ctx.out.say(current)
        ctx.out.set(key=key, value=current, source=ctx.source(key))
        return 0
    if value is None:
        raise Failure("config set needs a value", f'python tools/retrodev config set {key} <value> (or "" to reset)')
    values = {k: v for k, v in ctx.local.items() if k in ctx.policy["config"]}
    if value == "":
        values.pop(key, None)
    else:
        values[key] = value
    save_local(ctx.top, values)
    ctx.local = values
    ctx.out.say(f"{key} = {ctx.get(key)!r}  ({ctx.source(key)}; saved in {local_path(ctx.top)})")
    ctx.out.set(key=key, value=ctx.get(key), source=ctx.source(key))
    return 0

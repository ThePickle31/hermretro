"""Prepare and publish a release on the owner's words; see REFERENCE.md, Releases, for the gates.

Prepare, approve and land the version PR only if needed, wait for CI on the pinned commit, make the draft,
then verify and publish. A retry resumes the named version. A dry run changes nothing; --draft stops at the
draft. Next-version preparation is separate unless a stable release explicitly uses --with-next.
"""

from __future__ import annotations

import shlex
import time

from . import (
    approve,
    land,
    release,
    release_guard,
    release_next,
    release_publish,
    release_verify,
    repo,
    reviews,
    state,
    version_diff,
)
from .output import OWNER, WAITING, Failure, cmd


def command(
    words: str, rc: bool, version: str | None, dry_run: bool, draft: bool = False, with_next: bool = False
) -> str:
    """This command as an agent reruns it: the chosen version pinned, the owner's words quoted."""
    argv = ["python", "tools/retrodev", "release", "run"] + (["--rc"] if rc else [])
    argv += ["--version", release.stable(version)] if version else []
    argv += ["--owner-words", words] + (["--draft"] if draft else []) + (["--with-next"] if with_next else [])
    argv += ["--dry-run"] if dry_run else []
    return shlex.join(argv)


RERUN_START = 120.0  # seconds GitHub may take to start a requested rerun before the old failure counts again


def resumable(failure: Failure, again: str) -> Failure:
    """A step's own refusal (its message and FIX unchanged), then how to resume the whole release."""
    return Failure(failure.message, f"{failure.fix}; then {again} (it resumes)", failure.code, failure.data)


def version_only(ctx, old: str, new: str) -> str | None:
    """None when ``old``..``new`` changes only plugin.yaml's version line; else what it changes besides."""
    return version_diff.beyond_version(ctx.top, old, new)


def checked_head(ctx, info: dict, rec: dict, again: str) -> str:
    """The version pull request's head, once it is the recorded branch into the base and changes only the version."""
    number, branch, sha = info.get("number"), rec.get("branch"), info.get("headRefOid") or ""
    if info.get("headRefName") != branch or info.get("baseRefName") != ctx.base:
        raise Failure(
            f"#{number} is {info.get('headRefName')} into {info.get('baseRefName')}, not {branch} into {ctx.base}",
            f"ask the owner: the release record names #{number} for {branch}; nothing was approved",
            OWNER,
        )
    if not repo.ok(["cat-file", "-e", f"{sha}^{{commit}}"], ctx.top):
        raise Failure(f"#{number}'s head {sha[:9]} is not here", f"git fetch {ctx.remote}, then {again}")
    extra = version_only(ctx, repo.git(["merge-base", ctx.remote_base, sha], ctx.top).strip(), sha)
    if extra:
        raise Failure(
            f"the version pull request #{number} changes more than plugin.yaml's version line ({extra[:600]}): the "
            "owner's release words approve only that line, so nothing was approved",
            f"ask the owner; a release pull request changes only the version line: move the rest out of {branch} "
            f"(its own pull request), then {again}",
            OWNER,
            {"pr": number, "head": sha, "extra": extra},
        )
    found, wanted = release.version_at(ctx, sha), release.stable(rec["version"])
    if found != wanted:
        raise Failure(
            f"the version pull request #{number} sets version {found}, not {wanted}, the release these words were "
            "recorded for: nothing was approved",
            f"ask the owner; {branch} must set version: {wanted} (or start the release they name), then {again}",
            OWNER,
            {"pr": number, "head": sha, "version": found},
        )
    return sha


def unapprove(ctx, branch: str, number: int) -> None:
    record = state.load_branch(ctx.top, branch)
    record.pop("approval", None)
    state.save_branch(ctx.top, record)
    review = reviews.load(ctx, number)
    review.pop("approval", None)
    reviews.save(ctx, review)


class Run:
    def __init__(self, ctx, words: str, rc: bool, version: str, dry_run: bool, draft: bool, with_next: bool):
        self.ctx, self.words, self.rc, self.version, self.dry_run = ctx, words, rc, version, dry_run
        self.draft, self.with_next = draft, with_next
        self.checklist: str | None = None  # the owner's real-machine checklist result, for the notes
        self.again = command(words, rc, version, dry_run, draft, with_next)
        self.steps: list[dict] = []
        self.waiting = False  # a dry run past a step that is not done: the rest is only what it would do

    def step(self, name: str, status: str) -> None:
        self.steps.append({"step": name, "status": status})
        self.ctx.out.set(run_steps=self.steps)
        self.ctx.out.say(f"[{len(self.steps)} {name}] {status}")

    def would(self, name: str, what: str) -> None:
        self.waiting = True
        self.step(name, f"would run: {what}")

    def record(self) -> dict:
        return state.load_release(self.ctx.top, self.version) or {"version": self.version}

    def prepare(self, rec: dict) -> dict:
        if rec.get("pr") or rec.get("no_pr"):
            done = f"pull request #{rec['pr']}" if rec.get("pr") else "no version pull request was needed (no_pr)"
            self.step("prepare", f"done: {done}")
            return rec
        argv = ["python", "tools/retrodev", "release", "prepare"] + (["--rc"] if self.rc else [])
        argv += ["--version", release.stable(self.version), "--owner-words", self.words]
        if self.dry_run:  # prepare has no dry run of its own: say what it does, print nothing that would do it
            self.would("prepare", f"release prepare for {release.stable(self.version)} (the version pull request)")
            return rec
        self.ctx.out.say(f"running: {shlex.join(argv)}")
        try:
            release.prepare(self.ctx, self.words, rc=self.rc, named=release.stable(self.version))
        except Failure as failure:
            raise resumable(failure, self.again)
        rec = self.record()
        if not (rec.get("pr") or rec.get("no_pr")):
            raise Failure(f"release prepare recorded no pull request for {self.version}", self.again)
        self.step("prepare", "done: " + (f"pull request #{rec['pr']}" if rec.get("pr") else "no_pr"))
        return rec

    def approve_and_land(self, rec: dict) -> None:
        ctx = self.ctx
        if self.waiting or rec.get("no_pr"):
            why = "no version pull request" if rec.get("no_pr") else "after prepare"
            for name in ("approve", "land"):
                if rec.get("no_pr"):
                    self.step(name, f"skipped: {why}")
                else:
                    self.would(name, f"{name} the version pull request ({why})")
            return
        number = int(rec["pr"])
        info = reviews.pr_view(ctx, number)
        if info.get("state") == "MERGED":
            self.step("approve", f"done: #{number} is merged")
            if self.dry_run:
                self.step("land", f"done: #{number} is merged")
                return
            land.run(ctx, number)  # finishes what follows a merge (pull, gc), never merging again
            self.step("land", f"done: #{number} is merged")
            return
        if info.get("state") != "OPEN":
            raise Failure(
                f"the version pull request #{number} is {str(info.get('state')).lower()}",
                f"ask the owner: gh pr reopen {number}, then {self.again}",
                OWNER,
            )
        sha = checked_head(ctx, info, rec, self.again)
        branch = info["headRefName"]
        given = state.load_branch(ctx.top, branch).get("approval") or {}
        if given.get("pr") == number:
            self.step("approve", f'done: #{number} approved at {given.get("at")}: "{given.get("words")}"')
        elif self.dry_run:
            self.would("approve", f"approve #{number} with the owner's release words")
        else:
            # the release words, recorded as a release approval (scope release, this version: land_gates
            # release_scope_gate holds land to the version line, also when land runs on its own) before any GitHub call
            scope = {"scope": "release", "version": release.stable(rec["version"]), "checked": sha}
            approve.approve(ctx, number, self.words, scope=scope)  # it records the head it saw
            given = state.load_branch(ctx.top, branch).get("approval") or {}
            if given.get("head") != sha:
                unapprove(ctx, branch, number)
                raise Failure(
                    f"#{number}'s head moved while it was approved ({sha[:9]} checked, {str(given.get('head'))[:9]} "
                    "approved): the approval is withdrawn",
                    f"{self.again} (it checks the new head first)",
                )
            self.step("approve", f"done: #{number} at {sha[:9]}, with the owner's release words")
        if self.dry_run:
            self.would("land", cmd("python", "tools/retrodev", "land", number, "--dry-run"))
            return
        if checked_head(ctx, reviews.pr_view(ctx, number), rec, self.again) != sha:  # again, right before land
            raise Failure(f"#{number}'s head moved since it was checked", self.again)
        ctx.out.say(f"running: {cmd('python', 'tools/retrodev', 'land', number)}")
        try:
            land.run(ctx, number)
        except Failure as failure:
            raise resumable(failure, self.again)
        self.step("land", f"done: #{number} merged")

    def release_commit(self, rec: dict) -> str | None:
        ctx = self.ctx
        if self.waiting:
            self.would("wait", "wait for the push run on the release commit")
            return None
        rec = self.record()
        sha, gate = release_publish.commit_gate(ctx, rec, self.version, self.dry_run)
        if not sha:
            raise Failure(gate.message, f"{gate.fix}; then {self.again}", gate.code)
        if not self.dry_run and rec.get("sha") != sha:
            rec["sha"] = sha  # chosen once: publish releases this commit, whatever the base branch does meanwhile
            state.save_release(ctx.top, rec)
        if rec.get("pr"):
            extra = version_only(ctx, f"{sha}^1", sha)
            if extra:
                raise Failure(
                    f"the release commit {sha[:9]} changes more than plugin.yaml's version line ({extra[:600]})",
                    "stop and tell the owner: nothing was published",
                    OWNER,
                )
        return sha

    def wait(self, sha: str | None) -> None:
        if sha is None:
            return
        ctx = self.ctx
        settings = ctx.policy.get("release", {})
        poll, limit = float(settings.get("ci_poll", 30)), float(settings.get("ci_timeout", 1500))
        sleep, clock = ctx.fakes.get("sleep", time.sleep), ctx.fakes.get("clock", time.monotonic)
        started = clock()
        rerun_at: float | None = None  # when this run asked GitHub to rerun the failed jobs
        if not self.dry_run:
            ctx.out.say(f"waiting for the push run on {sha[:9]} (every {int(poll)} s, up to {int(limit)} s) ...")
        while True:
            gate = release_publish.ci_gate(ctx, sha)
            if gate.ok:
                self.step("wait", f"done: {gate.name} ({gate.message})")
                return
            if gate.code == WAITING:
                rerun_at = None  # the rerun is under way: its own result counts from here
            elif rerun_at is not None and clock() - rerun_at < RERUN_START:
                pass  # GitHub has not started the rerun yet: the old failure is still the newest
            elif not self.dry_run and release_guard.rerun(ctx, self.record(), sha, gate.message):
                rerun_at = clock()
            else:
                raise Failure(gate.message, f"{gate.fix}; then {self.again}", gate.code)
            if self.dry_run:
                self.would("wait", f"wait for the push run on {sha[:9]} ({gate.message})")
                return
            waited = clock() - started
            if waited >= limit:
                raise Failure(
                    f"CI is still running on the release commit {sha[:9]} after {int(waited)} s ({gate.message})",
                    f"run it again later: {self.again} (it resumes here)",
                    WAITING,
                    {"sha": sha},
                )
            sleep(min(poll, max(limit - waited, 0.0)))

    def publish(self) -> int:
        ctx, version = self.ctx, self.version
        argv = ["python", "tools/retrodev", "release", "publish", version]
        if self.waiting:
            self.would("publish", shlex.join(argv + ["--dry-run"]))
        else:
            ctx.out.say(f"running: {shlex.join(argv + (['--dry-run'] if self.dry_run else []))}")
            try:
                release_publish.run(ctx, version, dry_run=self.dry_run, checklist=self.checklist)
            except Failure as failure:
                raise resumable(failure, self.again)
            if self.dry_run:
                self.step("publish", "would run the commands above")
        if self.dry_run:
            if not self.draft:
                self.would("verify", f"release verify for {version}, then publish it (its checks first)")
                self.next_version()
            ctx.out.say("dry run: nothing was prepared, approved, merged, pushed, tagged or published")
            return 0
        url = (self.record().get("published_draft") or {}).get("url") or ""
        self.step("publish", f"done: draft release {url}")
        if self.draft:
            nxt = command(self.words, self.rc, self.version, False, with_next=self.with_next)
            self.ctx.out.set(url=url, next=nxt)
            self.ctx.out.say(f"draft release: {url}")
            self.ctx.out.say(f"next: read the draft with the owner; after their go: {nxt} (it publishes)")
            return 0
        return self.verify()

    def verify(self) -> int:
        """Step 6: release verify --publish, its checks first (the update check publish ran is reused)."""
        ctx, version = self.ctx, self.version
        try:
            release_guard.disclose_checklist(ctx, version)  # the notes say whether the checklist ran, before publishing
            ctx.out.say(f"running: {cmd('python', 'tools/retrodev', 'release', 'verify', version, '--publish')}")
            release_verify.run(ctx, version, publish=True)
        except Failure as failure:
            raise resumable(failure, self.again)
        url = (self.record().get("published") or {}).get("url") or ""
        self.step("verify", f"done: published {url}")
        ctx.out.set(url=url, published=True)
        ctx.out.say(f"published release: {url}")
        return self.next_version()

    def next_version(self) -> int:
        """Separate next-version work from verified publication; run inline only when explicitly requested."""
        if self.rc or (self.record().get("next") or {}).get("merged"):
            return 0
        followup = release_next.command(self.words, dry_run=self.dry_run, after=self.version)
        if self.dry_run and self.with_next:
            self.would("next", followup)
            return 0
        self.ctx.out.set(next_version={"status": "pending", "command": followup})
        if self.dry_run or not self.with_next:
            self.ctx.out.say(f"separate follow-up (next version): {followup}")
            return 0
        try:
            release_next.run(self.ctx, self.words, after=self.version)
        except Failure as failure:
            raise Failure(
                f"released, but dev did not move to the next version: {failure.message}",
                f"{failure.fix} (or {self.again}: it resumes at this step; without it, the next release opens its "
                "own version pull request)",
                failure.code,
                failure.data,
            )
        self.ctx.out.set(next_version={"status": "done"})
        self.step("next", f"done: {self.ctx.remote_base} says the next version")
        return 0


def run(
    ctx,
    words: str | None,
    rc: bool = False,
    named: str | None = None,
    dry_run: bool = False,
    draft: bool = False,
    checklist: str | None = None,
    with_next: bool = False,
) -> int:
    try:
        words = release.words_gate(words)
    except Failure as failure:
        shown = command("<their exact words>", rc, named, dry_run, draft, with_next)
        raise Failure(failure.message, f"ask the owner; when they ask for a release: {shown}", failure.code)
    if named and release.parse(named)[3] is not None:
        raise Failure(
            "--version takes X.Y.Z; --rc adds the -rc.M", command(words, True, None, dry_run, draft, with_next) + " ..."
        )
    if ctx.top.resolve() != ctx.main().resolve():
        raise Failure(
            f"release run runs from the main checkout ({ctx.main()}): land removes the release worktree",
            f"{cmd('cd', ctx.main())} && {command(words, rc, named, dry_run, draft, with_next)}",
        )
    if not dry_run:
        repo.git(["fetch", "--quiet", "--tags", ctx.remote], ctx.top)
    version = release_guard.choose(ctx, rc, named)
    flow = Run(ctx, words, rc, version, dry_run, draft, with_next)
    flow.checklist = checklist
    rec = flow.record()
    ctx.out.set(version=version, dry_run=dry_run, resume=flow.again)
    ctx.out.say(f"release {version}" + (" (dry run)" if dry_run else "") + f": {flow.again}")
    if rec.get("published"):
        if dry_run:
            ctx.out.say(f"{version} is recorded as published")
            return 0
        try:
            info = release_verify.published_view(ctx, version)
        except Failure as failure:
            raise resumable(failure, flow.again)
        ctx.out.set(url=info["url"], published=True)
        ctx.out.say(f"{version} is published already ({info['url']})")
        return 0 if draft else flow.next_version()
    if not rec.get("run"):  # a new release: something to release, and no next-version pull request in its way
        if not release_guard.news(ctx):
            previous = release.previous_stable(ctx)
            moved = release.version_at(ctx, ctx.remote_base) != previous
            raise Failure(
                f"nothing to release: {ctx.remote_base} has no change since v{previous} besides the version line",
                "land a change first; a release needs something new for users"
                + ("" if moved else f" (to move dev on after v{previous}: {release_next.command(words)})"),
            )
        release_guard.stale_next(ctx, version, dry_run)
    if checklist and checklist.strip() and not dry_run:  # kept before any step: a resumed run still has it
        rec["checklist"] = checklist.strip()
        state.save_release(ctx.top, rec)
    if not dry_run and not rec.get("run"):
        rec.update(run={"at": state.now()}, rc=rc)  # the release this command works on, before any step acts
        state.save_release(ctx.top, rec)
    rec = flow.prepare(rec)
    flow.approve_and_land(rec)
    flow.wait(flow.release_commit(rec))
    return flow.publish()

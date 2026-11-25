"""The releases RPC's reading of GitHub's releases: stable ones only, newest first, their notes cut down to what users
see, kept for a while, and a failure answered without raising."""

import io
import json
import unittest

from backend.setup import releases

BODY = """<!-- Release notes generated using configuration in .github/release.yml at v1.4.13 -->

## What's Changed
### Changes
* feat(library): give every game folder the publishable game layout by @someone in https://github.com/o/r/pull/175
* fix(build): write every project build to the game's one ROM by @someone in https://github.com/o/r/pull/174
* feat(dev): a sandbox Hermes that drives the real page headless by @someone in https://github.com/o/r/pull/131
* docs(dev): the developer docs become development skills by @someone in https://github.com/o/r/pull/138
* chore(engine): the maintainer may change the engine by @someone in https://github.com/o/r/pull/144
* fix: a bare fix with no scope

**Full Changelog**: https://github.com/o/r/compare/v1.4.12...v1.4.13
"""


def row(tag, **extra):
    return {
        "tag_name": tag,
        "published_at": "2026-11-24T04:00:00Z",
        "html_url": f"https://x/{tag}",
        "body": "",
        **extra,
    }


class Opener:
    def __init__(self, rows=None, error=None):
        self.rows, self.error, self.calls = rows, error, 0

    def __call__(self, request, timeout):
        self.calls += 1
        if self.error:
            raise self.error
        return io.BytesIO(json.dumps(self.rows).encode())


class ReleasesTest(unittest.TestCase):
    def setUp(self):
        releases.forget()
        self.addCleanup(releases.forget)

    def test_notes_keep_new_and_fixed_lines_for_users(self):
        self.assertEqual(
            releases.notes(BODY),
            [
                {"kind": "new", "text": "Give every game folder the publishable game layout"},
                {"kind": "fixed", "text": "Write every project build to the game's one ROM"},
                {"kind": "fixed", "text": "A bare fix with no scope"},
            ],
        )

    def test_only_stable_published_releases_newest_first(self):
        rows = [
            row("v1.4.9"),
            row("v1.4.13", body=BODY),
            row("v1.4.12"),
            row("v1.4.14", draft=True),
            row("v1.4.14-rc.1", prerelease=True),
            row("nightly"),
        ]
        answer = releases.latest(opener=Opener(rows))
        self.assertTrue(answer["ok"])
        self.assertEqual([r["version"] for r in answer["releases"]], ["1.4.13", "1.4.12", "1.4.9"])
        self.assertEqual(answer["releases"][0]["url"], "https://x/v1.4.13")
        self.assertEqual(len(answer["releases"][0]["notes"]), 3)

    def test_an_answer_is_kept_for_a_while_and_a_failure_is_not(self):
        clock = [1000.0]
        failing = Opener(error=OSError("offline"))
        self.assertEqual(releases.latest(opener=failing, now=lambda: clock[0])["ok"], False)
        working = Opener([row("v1.4.1")])
        releases.latest(opener=working, now=lambda: clock[0])
        clock[0] += releases.CACHE_SECONDS - 1
        releases.latest(opener=working, now=lambda: clock[0])
        self.assertEqual(working.calls, 1)
        clock[0] += 2
        releases.latest(opener=working, now=lambda: clock[0])
        self.assertEqual(working.calls, 2)

    def test_callers_at_the_same_time_share_one_request(self):
        import threading

        started, release = threading.Event(), threading.Event()

        class Slow(Opener):
            def __call__(self, request, timeout):
                started.set()
                release.wait(5)
                return super().__call__(request, timeout)

        slow = Slow([row("v1.4.1")])
        answers = []
        threads = [threading.Thread(target=lambda: answers.append(releases.latest(opener=slow))) for _ in range(3)]
        threads[0].start()
        started.wait(5)
        for thread in threads[1:]:
            thread.start()
        release.set()
        for thread in threads:
            thread.join(5)
        self.assertEqual(slow.calls, 1)
        self.assertEqual(len(answers), 3)


if __name__ == "__main__":
    unittest.main()

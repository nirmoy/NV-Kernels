#!/usr/bin/env python3
"""Black-box regression tests for validate-pr cherry-pick matching."""

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest


VALIDATE_PR = pathlib.Path(__file__).with_name("validate-pr")
SUBJECT = "fixture: insert payload"
UPSTREAM_SOB = "Signed-off-by: Upstream Author <upstream@example.com>"
LOCAL_SOB = "Signed-off-by: Local Author <local@example.com>"


class ValidatePrPatchIdTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = pathlib.Path(self._tmp.name)
        self.real_git = shutil.which("git")
        self.assertIsNotNone(self.real_git)

        self._git("init")
        self._set_identity("Fixture Author", "fixture@example.com")
        self._write_fixture([
            "first-before",
            "anchor",
            "first-after",
            "spacer-1",
            "spacer-2",
            "spacer-3",
            "spacer-4",
            "second-before",
            "anchor",
            "second-after",
        ])
        self.base = self._commit("fixture: base", LOCAL_SOB)

    def _git(self, *args, input_text=None):
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            input=input_text,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            self.fail(
                "git {} failed ({}):\n{}{}".format(
                    " ".join(args), result.returncode,
                    result.stdout, result.stderr))
        return result.stdout.strip()

    def _set_identity(self, name, email):
        self._git("config", "user.name", name)
        self._git("config", "user.email", email)

    def _write_fixture(self, lines):
        (self.repo / "fixture.txt").write_text("\n".join(lines) + "\n")

    def _read_fixture(self):
        return (self.repo / "fixture.txt").read_text().splitlines()

    def _commit(self, subject, body):
        self._git("add", "fixture.txt")
        self._git("commit", "-F", "-",
                  input_text="{}\n\n{}\n".format(subject, body))
        return self._git("rev-parse", "HEAD")

    def _build_case(self, change, context_parent=True):
        self._git("checkout", "-b", "upstream-topic", self.base)
        self._set_identity("Upstream Author", "upstream@example.com")
        lines = self._read_fixture()
        lines.insert(lines.index("anchor") + 1, "payload")
        self._write_fixture(lines)
        upstream = self._commit(SUBJECT, UPSTREAM_SOB)
        self._git("update-ref", "refs/remotes/upstream/linux", upstream)

        self._git("checkout", "-b", "local", self.base)
        self._set_identity("Local Author", "local@example.com")
        if context_parent:
            lines = self._read_fixture()
            lines[0] = "local-first-before"
            self._write_fixture(lines)
            self._commit("fixture: adjust local context", LOCAL_SOB)
        parent = self._git("rev-parse", "HEAD")

        if change == "exact":
            self._git("cherry-pick", "-x", "--signoff", upstream)
        else:
            lines = self._read_fixture()
            anchors = [i for i, line in enumerate(lines) if line == "anchor"]
            if change == "context":
                lines.insert(anchors[0] + 1, "payload")
            elif change == "mutated":
                lines.insert(anchors[0] + 1, "payload-mutated")
            elif change == "wrong-occurrence":
                lines.insert(anchors[1] + 1, "payload")
            else:
                self.fail("unknown fixture change: {}".format(change))
            self._write_fixture(lines)
            self._commit(
                SUBJECT,
                "{}\n\n(cherry picked from commit {})\n{}".format(
                    UPSTREAM_SOB, upstream, LOCAL_SOB))

        local = self._git("rev-parse", "HEAD")
        return parent, local

    def _fake_git_env(self, mode):
        fake_bin = self.repo / "fake-bin"
        fake_bin.mkdir(exist_ok=True)
        wrapper = fake_bin / "git"
        wrapper.write_text("""#!/usr/bin/env python3
import os
import subprocess
import sys

real_git = os.environ["VALIDATE_PR_REAL_GIT"]
mode = os.environ["VALIDATE_PR_FAKE_GIT_MODE"]
args = sys.argv[1:]

if mode == "show-failure" and args and args[0] == "show":
    result = subprocess.run([real_git, *args], capture_output=True)
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    sys.exit(1)

if (args[:2] == ["patch-id", "--stable"] and
        mode in ("patch-id-malformed", "patch-id-extra-line")):
    sys.stdin.buffer.read()
    if mode == "patch-id-malformed":
        sys.stdout.write("not-a-patch-id not-a-commit-id\\n")
        sys.exit(0)
    if mode == "patch-id-extra-line":
        sys.stdout.write("{} {}\\n{} {}\\n".format(
            "a" * 40, "b" * 40, "c" * 40, "d" * 40))
        sys.exit(0)

if mode == "merge-tree-extra-line" and args and args[0] == "merge-tree":
    result = subprocess.run([real_git, *args], capture_output=True)
    sys.stdout.buffer.write(result.stdout)
    if result.stdout and not result.stdout.endswith(b"\\n"):
        sys.stdout.buffer.write(b"\\n")
    sys.stdout.buffer.write(b"unexpected-extra-line\\n")
    sys.stderr.buffer.write(result.stderr)
    sys.exit(result.returncode)

os.execv(real_git, [real_git, *args])
""")
        wrapper.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
        env["VALIDATE_PR_REAL_GIT"] = self.real_git
        env["VALIDATE_PR_FAKE_GIT_MODE"] = mode
        return env

    def _validate(self, parent, local, git_mode=None):
        return subprocess.run(
            [sys.executable, str(VALIDATE_PR),
             "{}..{}".format(parent, local), "upstream", "linux",
             "--no-update"],
            cwd=self.repo,
            env=self._fake_git_env(git_mode) if git_mode else None,
            text=True,
            capture_output=True,
        )

    @staticmethod
    def _output(result):
        return "stdout:\n{}\nstderr:\n{}".format(
            result.stdout, result.stderr)

    def _patch_id_status(self, result, local):
        marker = "│ {} │".format(local[:12])
        for line in result.stdout.splitlines():
            if marker in line:
                cells = line.split("│")
                self.assertGreaterEqual(len(cells), 6, self._output(result))
                return cells[3].strip()
        self.fail("no digest row for {}:\n{}".format(
            local[:12], self._output(result)))

    def test_accepts_context_only_replay(self):
        parent, local = self._build_case("context")

        result = self._validate(parent, local)

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._patch_id_status(result, local), "context")

    def test_accepts_exact_cherry_pick(self):
        parent, local = self._build_case("exact", context_parent=False)

        result = self._validate(parent, local)

        self.assertEqual(result.returncode, 0, self._output(result))
        self.assertEqual(self._patch_id_status(result, local), "match")

    def test_rejects_git_show_failure_with_patch_output(self):
        parent, local = self._build_case("exact", context_parent=False)

        result = self._validate(parent, local, "show-failure")

        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertIn("patch-ID mismatch with upstream", result.stdout)

    def test_rejects_malformed_patch_id_output(self):
        parent, local = self._build_case("exact", context_parent=False)

        result = self._validate(parent, local, "patch-id-malformed")

        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertIn("patch-ID mismatch with upstream", result.stdout)

    def test_rejects_merge_tree_output_with_extra_line(self):
        parent, local = self._build_case("context")

        result = self._validate(parent, local, "merge-tree-extra-line")

        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertIn("patch-ID mismatch with upstream", result.stdout)

    def test_rejects_multiple_patch_id_output_lines(self):
        parent, local = self._build_case("exact", context_parent=False)

        result = self._validate(parent, local, "patch-id-extra-line")

        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertIn("patch-ID mismatch with upstream", result.stdout)

    def test_rejects_mutated_payload(self):
        parent, local = self._build_case("mutated")

        result = self._validate(parent, local)

        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertIn("patch-ID mismatch with upstream", result.stdout)

    def test_rejects_same_change_at_different_occurrence(self):
        parent, local = self._build_case("wrong-occurrence")

        result = self._validate(parent, local)

        self.assertEqual(result.returncode, 1, self._output(result))
        self.assertIn("patch-ID mismatch with upstream", result.stdout)


if __name__ == "__main__":
    unittest.main()

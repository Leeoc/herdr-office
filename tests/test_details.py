import os
import unittest

from office.details import pane_story, short_step

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def sample(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return [line for line in f.read().splitlines() if line.strip()]


class PaneStoryTest(unittest.TestCase):
    def test_working_pane(self):
        story = pane_story(sample("claude_working.txt"))
        self.assertEqual(story["asked"], "add a retry to the upload client and run the tests")
        self.assertEqual(story["step"], "running uv run pytest -q tests/storage")
        self.assertTrue(story["status"].startswith("Percolating…"))
        self.assertNotIn("question", story)

    def test_unsent_suggestion_in_the_prompt_box_is_not_the_task(self):
        story = pane_story(sample("claude_done_with_suggestion.txt"))
        self.assertEqual(story["asked"], "write the release notes for v0.12.0")
        self.assertEqual(story["status"], "Brewed for 1m 12s")
        self.assertNotIn("question", story)

    def test_permission_prompt_is_the_question(self):
        story = pane_story(sample("claude_blocked.txt"))
        self.assertEqual(story["question"], "Do you want to proceed?")
        self.assertEqual(story["asked"], "tidy up the old migrations")

    def test_empty_pane(self):
        self.assertEqual(pane_story([]), {})


class ShortStepTest(unittest.TestCase):
    def test_tools_become_verbs(self):
        self.assertEqual(short_step("Read(src/a/b.py)"), "reading b.py")
        self.assertEqual(short_step("Bash(cd x && make test)"), "running make test")
        self.assertEqual(short_step("Grep(pattern)"), "searching pattern")

    def test_plain_text_stays(self):
        self.assertEqual(short_step("All done, the tests pass."), "All done, the tests pass.")


if __name__ == "__main__":
    unittest.main()

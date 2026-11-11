"""Regression tests for verification and recovery decisions using journal records."""
import unittest

from backend import plan_runner


class PlanEvidence(unittest.TestCase):
    def test_change_requires_a_new_command_check(self):
        check = {"type": "command", "command": "python -m unittest"}
        passed = {
            "name": "run_command",
            "args": {"command": check["command"]},
            "status": "done",
            "result": {"exit_code": 0},
        }
        edit = {"name": "edit_file", "args": {"path": "app.py"}, "status": "done"}
        read = {"name": "read_file", "args": {"path": "app.py"}, "status": "done"}
        for actions, expected in [
            ([passed, edit], "not_run"),
            ([passed, read], "passed"),
            ([passed, edit, passed], "passed"),
        ]:
            with self.subTest(expected=expected, actions=actions):
                self.assertEqual(plan_runner.run_check(check, actions, None)[0], expected)

    def test_revising_the_check_discards_its_verdict(self):
        step = {"id": "s1", "title": "Build", "check": {"type": "file_exists", "path": "a"}}
        saved = {"steps": [{**step, "status": "done", "verdict": "passed"}]}
        revised = {**step, "status": "done", "check": {"type": "file_exists", "path": "b"}}
        merged, = plan_runner.merge_plan(saved, [revised], plan_run=False)
        self.assertEqual(merged["status"], "pending")
        self.assertNotIn("verdict", merged)

    def test_interrupted_privileged_operation_blocks_even_if_the_check_passes(self):
        actions = [{"name": "admin_task", "status": "interrupted"}]
        decision, verdict, reason = plan_runner.judge({}, actions, {}, "passed", "", None, "", 1)
        self.assertEqual((decision, verdict), ("blocked", None))
        self.assertIn("outcome is unknown", reason)

    def test_required_check_blocks_after_retries(self):
        decision, verdict, reason = plan_runner.judge(
            {}, [], {}, "not_run", "Run the check again.", "same", "same", 2
        )
        self.assertEqual((decision, verdict, reason), ("blocked", "unverified", "Run the check again."))

    def test_cycle_has_no_executable_order(self):
        with self.assertRaisesRegex(ValueError, 'cycle'):
            plan_runner.step_order([
                {'id': 'a', 'depends_on': ['b']},
                {'id': 'b', 'depends_on': ['a']},
            ])

    def test_command_evidence_binds_to_exact_arguments_and_staged_inputs(self):
        check = {"type": "command", "command": "python -c 'print(1)'", "python": True, "inputs": ["fixture.txt"]}
        args = {k: v for k, v in check.items() if k != "type"}
        self.assertTrue(plan_runner.check_command_matches(check, args))
        self.assertFalse(plan_runner.check_command_matches(check, {**args, "inputs": ["alternate.txt"]}))
        self.assertFalse(plan_runner.check_command_matches(check, {**args, "python": False}))
        self.assertFalse(plan_runner.check_command_matches(check, {**args, "command": check["command"].upper()}))

    def test_a_deduplicated_command_is_not_fresh_verification(self):
        check = {"type": "command", "command": "python -m unittest"}
        replay = {"name": "run_command", "args": {"command": check["command"]},
                  "status": "done", "result": {"replayed": True}}
        self.assertEqual(plan_runner.run_check(check, [replay], None)[0], "not_run")

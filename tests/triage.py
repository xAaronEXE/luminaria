import unittest

from backend.triage import classify


class Triage(unittest.TestCase):
    def test_clear_intents_have_distinct_lanes(self):
        self.assertEqual(classify('Hello!'), 'answer')
        self.assertEqual(classify('Look up the latest Python release'), 'research')
        self.assertEqual(classify('Make a plan for a CSV converter'), 'plan')
        self.assertEqual(classify('Publish the new build'), 'plan')
        self.assertEqual(classify('Fix the parser'), 'do')

    def test_short_spoken_definitions_can_use_the_voice_model(self):
        self.assertEqual(classify('What is a palindrome?', spoken=True), 'answer')
        self.assertEqual(classify('What is a palindrome?'), 'do')
        self.assertEqual(classify('Define my project requirements', spoken=True), 'do')
        self.assertEqual(classify('What is a palindrome and write a test', spoken=True), 'do')

    def test_mixed_requests_and_attached_content_stay_on_normal_path(self):
        self.assertEqual(classify('Research the bug and implement the fix'), 'do')
        self.assertEqual(classify('Write a plan and implement it'), 'do')
        self.assertEqual(classify([{'type': 'text', 'text': 'Deploy this'}]), 'do')

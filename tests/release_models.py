import unittest
from unittest.mock import patch

from backend.model_profiles import generation_options, model_family
from backend.public_scores import public_score


class ReleaseModelProfiles(unittest.TestCase):
    def test_qwen3_hybrid_has_its_own_thinking_options(self):
        model = {'id': 'qwen3-8b-q4_k_m'}
        self.assertEqual(model_family(model), 'qwen3')
        self.assertEqual(generation_options(model, True)['chat_template_kwargs'], {'enable_thinking': True})
        self.assertEqual(generation_options(model, False)['top_p'], 0.8)

    def test_other_families_keep_their_embedded_template(self):
        for name in ('Meta-Llama-3.1-8B-Instruct', 'Gemma 3 4B', 'DeepSeek-R1', 'Qwen3.5-9B', 'Qwen3-Coder-30B'):
            with self.subTest(name=name):
                self.assertEqual(generation_options({'name': name}, True), {})

    def test_public_score_requires_an_exact_standard_model_match(self):
        score = {'name': 'Qwen3.5-9B', 'eci': 139.35, 'low': 138, 'high': 141}
        with patch('backend.public_scores.catalog', return_value={'qwen359b': score}):
            self.assertEqual(public_score({'name': 'Qwen3.5 9B', 'variant': 'standard'}), score)
            self.assertIsNone(public_score({'name': 'Qwen3.5 9B', 'variant': 'abliterated'}))
            self.assertIsNone(public_score({'name': 'Qwen3.5 4B', 'variant': 'standard'}))

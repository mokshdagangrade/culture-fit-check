import unittest

from prepare_data import split_examples
from train import encode_example


class SplitTests(unittest.TestCase):
    def test_training_masks_prompt_and_excludes_overlength(self):
        class Tokenizer:
            def apply_chat_template(self, messages, tokenize, add_generation_prompt):
                return [1, 2, 3] if add_generation_prompt else [1, 2, 3, 4, 5]
        messages = [{'role': 'user', 'content': 'Brief'}, {'role': 'assistant', 'content': 'Copy'}]
        row = encode_example(messages, Tokenizer(), 5)
        self.assertEqual(row['labels'], [-100, -100, -100, 4, 5])
        self.assertIsNone(encode_example(messages, Tokenizer(), 4))

    def test_transitive_duplicates_and_brands_stay_together(self):
        rows = [{"id": str(i), "source": "test", "brand": "",
                 "prompt_key": f"p{i}", "completion_key": f"c{i}"} for i in range(100)]
        # Chain prompt -> completion -> brand; all four must stay together.
        rows[1]["prompt_key"] = rows[0]["prompt_key"]
        rows[2]["completion_key"] = rows[1]["completion_key"]
        rows[2]["brand"] = "Example Brand"
        rows[3]["brand"] = "example brand"
        splits = split_examples(rows)
        locations = {row["id"]: name for name, group in splits.items() for row in group}
        self.assertEqual(len(set(locations[str(i)] for i in range(4))), 1)
        self.assertEqual(len(locations), len(rows))
        self.assertTrue(all(splits.values()))
        self.assertEqual(splits, split_examples(rows))


if __name__ == "__main__":
    unittest.main()

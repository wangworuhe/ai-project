import unittest

from backend.services.grammar_grading_service import grade_answer_values


TEXT_SLOT = [{
    "key": "answer-1",
    "normalization_rule": "english-text",
    "points": "1.00",
}]


class GrammarGradingTest(unittest.TestCase):
    def grade(self, value, accepted):
        variants = [
            {"order": index, "values": {"answer-1": answer}}
            for index, answer in enumerate(accepted, start=1)
        ]
        return grade_answer_values(
            TEXT_SLOT, {"answer-1": value}, variants, "normalized"
        )

    def test_normalizes_only_safe_presentation_differences(self):
        result = self.grade("  WHY ARE YOU CRYING ?  ", ["Why are you crying?"])
        self.assertEqual(result["outcome"], "correct")
        self.assertEqual(
            self.grade("Why are you crying", ["Why are you crying?"])["outcome"],
            "correct",
        )
        self.assertEqual(
            self.grade("Why are you crying.", ["Why are you crying?"])["outcome"],
            "incorrect",
        )
        self.assertEqual(
            self.grade("He's tying.", ["He's tying"])["outcome"],
            "incorrect",
        )

    def test_curly_and_straight_apostrophes_match(self):
        result = self.grade("I’m not listening", ["I'm not listening"])
        self.assertEqual(result["outcome"], "correct")

    def test_contractions_require_an_explicit_variant(self):
        result = self.grade("I am not listening", ["I'm not listening"])
        self.assertEqual(result["outcome"], "incorrect")

    def test_does_not_correct_spelling_or_word_order(self):
        self.assertEqual(
            self.grade("Why are you cring?", ["Why are you crying?"])["outcome"],
            "incorrect",
        )
        self.assertEqual(
            self.grade("Why you are crying?", ["Why are you crying?"])["outcome"],
            "incorrect",
        )

    def test_multi_slot_variants_cannot_be_cross_combined(self):
        slots = [
            {"key": "answer-1", "normalization_rule": "english-text"},
            {"key": "answer-2", "normalization_rule": "english-text"},
        ]
        variants = [
            {"order": 1, "values": {"answer-1": "takes", "answer-2": "does it take"}},
            {"order": 2, "values": {"answer-1": "took", "answer-2": "did it take"}},
        ]
        result = grade_answer_values(
            slots,
            {"answer-1": "takes", "answer-2": "did it take"},
            variants,
            "normalized",
        )
        self.assertEqual(result["outcome"], "incorrect")

    def test_blank_and_partial_multi_slot_answers_are_distinct(self):
        slots = [
            {"key": "answer-1", "normalization_rule": "english-text"},
            {"key": "answer-2", "normalization_rule": "english-text"},
        ]
        variants = [{
            "order": 1,
            "values": {"answer-1": "takes", "answer-2": "does it take"},
        }]
        self.assertEqual(
            grade_answer_values(slots, {}, variants, "normalized")["outcome"],
            "unanswered",
        )
        self.assertEqual(
            grade_answer_values(
                slots, {"answer-1": "takes"}, variants, "normalized"
            )["outcome"],
            "incomplete",
        )

    def test_choice_codes_are_case_insensitive_but_exact(self):
        slots = [{"key": "answer-1", "normalization_rule": "choice-code"}]
        variants = [{"order": 1, "values": {"answer-1": "e"}}]
        self.assertEqual(
            grade_answer_values(
                slots, {"answer-1": " E "}, variants, "exact"
            )["outcome"],
            "correct",
        )
        self.assertEqual(
            grade_answer_values(
                slots, {"answer-1": "option e"}, variants, "exact"
            )["outcome"],
            "incorrect",
        )


if __name__ == "__main__":
    unittest.main()

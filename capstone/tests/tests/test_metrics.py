from core.metrics import (compute_groundedness, compute_usefulness,
                          compute_accuracy, evaluate_answer, extractive_answer)

CTX = ("The scheme gives a subsidy of INR 5000 per hectare to enrolled farmers. "
       "The minimum support price is INR 3846 per quintal.")

def test_groundedness_full_when_quoted():
    assert compute_groundedness("subsidy of INR 5000 per hectare", CTX) > 0.6

def test_groundedness_zero_for_empty():
    assert compute_groundedness("", CTX) == 0.0

def test_usefulness_low_for_punt():
    assert compute_usefulness("I cannot answer that.") <= 0.2

def test_usefulness_high_for_substantive():
    assert compute_usefulness("The subsidy is INR 5000 per hectare for enrolled "
                              "farmers, with procurement at a minimum support price.") >= 0.7

def test_accuracy_is_mean_of_three():
    assert compute_accuracy(0.6, 0.6, 0.6) == 0.6
    assert 0.0 <= compute_accuracy(1, 0, 0.5) <= 1.0

def test_evaluate_answer_keys():
    m = evaluate_answer("subsidy INR 5000 per hectare", CTX, 0.8)
    for k in ("confidence", "groundedness", "usefulness", "accuracy_score"):
        assert k in m

def test_extractive_answer_finds_relevant_sentence():
    out = extractive_answer("what is the subsidy?", CTX)
    assert "5000" in out["answer"]
    assert out["used_fallback"] is True

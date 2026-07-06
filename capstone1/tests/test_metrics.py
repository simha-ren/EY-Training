"""Unit tests for core.metrics — evaluation scoring is deterministic."""
from core import metrics


def test_groundedness_high_when_answer_from_context():
    context = "Farmers get crop loans at 4% interest under the Kisan scheme."
    answer = "Farmers get crop loans at 4% interest."
    score = metrics.compute_groundedness(answer, context)
    assert 0.0 <= score <= 1.0
    assert score > 0.5  # answer words are drawn from the context


def test_groundedness_low_when_answer_unrelated():
    context = "The healthcare policy covers cashless hospitalization."
    answer = "Quantum entanglement enables faster than light communication."
    score = metrics.compute_groundedness(answer, context)
    assert score < 0.5


def test_usefulness_bounded():
    assert 0.0 <= metrics.compute_usefulness("") <= 1.0
    long_answer = "This is a reasonably detailed and specific answer. " * 5
    assert metrics.compute_usefulness(long_answer) > 0.0


def test_accuracy_is_mean_of_components():
    acc = metrics.compute_accuracy(0.6, 0.9, 0.3)
    assert abs(acc - (0.6 + 0.9 + 0.3) / 3) < 1e-9


def test_evaluate_answer_shape():
    result = metrics.evaluate_answer(
        "Crop loans are available at 4% interest.",
        "Farmers get crop loans at 4% interest.",
        confidence=0.8,
    )
    for key in ("confidence", "groundedness", "usefulness", "accuracy_score"):
        assert key in result
        assert 0.0 <= result[key] <= 1.0


def test_extractive_answer_returns_grounded_text():
    context = (
        "The Kisan Credit Card scheme offers crop loans up to 3 lakh. "
        "Insurance claims are processed within 30 days. "
        "Soil testing is recommended before sowing."
    )
    out = metrics.extractive_answer("How much can farmers borrow?", context)
    assert isinstance(out, dict)
    assert "answer" in out
    assert out["answer"]  # non-empty

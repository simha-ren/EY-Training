#!/usr/bin/env python3
"""
FinSight AI — CI Evaluation Runner
Invoked by GitHub Actions on every PR.
Exit code 0 = quality gate passed; Exit code 1 = gate failed.
"""

import sys
import json
import csv
import os
from pathlib import Path

# Add src/ to path when running from repo root
sys.path.insert(0, str(Path(__file__).parent))

from eval_harness import run_eval, build_leaderboard, check_quality_gate, GROQ_MODELS
from test_cases import SMOKE_TEST_CASES, TEST_CASES

RESULTS_DIR = Path("results")
if not RESULTS_DIR.is_absolute():
    # Make sure we write to the results directory relative to this script's parent (colab3 root)
    RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ── Config ───────────────────────────────────────────────────────────
# Use smoke test (5 easy cases) in CI for speed; full suite on schedule
CI_MODE = os.environ.get("EVAL_MODE", "smoke")  # "smoke" | "full"
test_cases = SMOKE_TEST_CASES if CI_MODE == "smoke" else TEST_CASES

# In CI, only run the two fastest models to save cost + time
CI_MODELS = {
    "llama-3.3-70b": GROQ_MODELS["llama-3.3-70b"],  # Quality model
    "llama-3.1-8b":  GROQ_MODELS["llama-3.1-8b"],   # Speed model
}

print(f"[FinSight CI] Mode: {CI_MODE} | Cases: {len(test_cases)} | Models: {list(CI_MODELS.keys())}")


def save_results_csv(results: list, path: Path) -> None:
    if not results: return
    keys = list(results[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)
    print(f"  Saved: {path}")


def save_leaderboard_json(leaderboard: list, path: Path) -> None:
    with open(path, "w") as f:
        json.dump(leaderboard, f, indent=2)
    print(f"  Saved: {path}")


def print_summary(leaderboard: list, gate: dict) -> None:
    print("\n" + "="*65)
    print("  FINSIGHT CI EVAL SUMMARY")
    print("="*65)
    header = f"{'Model':<20} {'Composite':>10} {'BERTScore':>10} {'Hallucin%':>10} {'p95(s)':>8} {'Cost$':>8} {'Pass':>5}"
    print(header)
    print("-"*65)
    for row in leaderboard:
        composite = f"{row['composite']:.2f}" if row.get('composite') else "N/A"
        bert      = f"{row['bert_score']:.3f}" if row.get('bert_score') is not None else "N/A"
        hall      = f"{row['hallucin_rate']*100:.1f}%" if row.get('hallucin_rate') is not None else "N/A"
        p95       = f"{row['latency_p95']:.2f}" if row.get('latency_p95') else "N/A"
        cost      = f"${row['avg_cost']:.5f}" if row.get('avg_cost') is not None else "N/A"
        passed    = "✅" if row.get("meets_constraints") else "❌"
        print(f"{row['model']:<20} {composite:>10} {bert:>10} {hall:>10} {p95:>8} {cost:>8} {passed:>5}")
    print("="*65)
    status = "✅ PASSED" if gate["passed"] else "❌ FAILED"
    print(f"\nQuality Gate: {status}")
    print(f"Reason: {gate['reason']}")
    if gate.get("best_model"):
        print(f"Recommended model: {gate['best_model']}")
    print()


def main() -> int:
    print("[FinSight CI] Running evaluation harness...")
    results = run_eval(test_cases, models=CI_MODELS, judge=True)

    save_results_csv(results, RESULTS_DIR / "ci_eval_results.csv")

    leaderboard = build_leaderboard(results)
    save_leaderboard_json(leaderboard, RESULTS_DIR / "ci_leaderboard.json")

    gate = check_quality_gate(leaderboard)
    print_summary(leaderboard, gate)

    # Write gate outcome for downstream steps / GitHub Summary
    with open(RESULTS_DIR / "gate_outcome.json", "w") as f:
        json.dump(gate, f, indent=2)

    # Append to GitHub Step Summary if running in Actions
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        with open(gh_summary, "a") as f:
            f.write(f"## FinSight Eval — Quality Gate: {'✅ PASSED' if gate['passed'] else '❌ FAILED'}\n\n")
            f.write(f"**{gate['reason']}**\n\n")
            f.write("| Model | Composite | BERTScore | Hallucin% | p95 | Cost | Pass |\n")
            f.write("|---|---|---|---|---|---|---|\n")
            for row in leaderboard:
                composite = f"{row['composite']:.2f}" if row.get('composite') else "N/A"
                bert = f"{row['bert_score']:.3f}" if row.get('bert_score') is not None else "N/A"
                hall = f"{row['hallucin_rate']*100:.1f}%" if row.get('hallucin_rate') is not None else "N/A"
                p95  = f"{row['latency_p95']:.2f}s"
                cost = f"${row['avg_cost']:.5f}"
                icon = "✅" if row.get("meets_constraints") else "❌"
                f.write(f"| {row['model']} | {composite} | {bert} | {hall} | {p95} | {cost} | {icon} |\n")

    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

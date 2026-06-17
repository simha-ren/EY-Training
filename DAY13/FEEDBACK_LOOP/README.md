# FinSight AI: LLM Prompt Engineering Feedback Loop

## Project Overview

This project implements a feedback loop to evaluate and compare different Large Language Model (LLM) prompt versions for generating credit risk memos.

The objective is to systematically identify and mitigate common LLM issues such as:

- Hallucination
- Missing information
- Incorrect output structure
- Non-compliant financial reporting formats

The system enables iterative prompt engineering improvements for financial AI applications by measuring output quality, tracking failures, and comparing prompt versions quantitatively.

---

# Purpose

The core purpose of this notebook is to:

1. **Simulate LLM Performance**
   - Execute multiple prompt versions against predefined borrower profiles.
   - Evaluate generated credit risk memos under controlled scenarios.

2. **Automated Quality Probing**
   - Programmatically evaluate LLM outputs using predefined metrics:
     - Hallucination detection
     - Missing section detection
     - Output length validation
     - User correction simulation

3. **Log and Analyze Results**
   - Store every LLM interaction and evaluation result in a SQLite database.
   - Maintain structured records for auditing and analysis.

4. **Compare Prompt Versions**
   - Measure improvements between:
     - Baseline prompt (`v1.0`)
     - Enhanced prompt (`v2.0`)

5. **Visualize Outcomes**
   - Generate charts showing:
     - Failure distribution
     - Quality improvements
     - Before vs after comparison

---

# Architecture Overview

The system follows a simulation and evaluation pipeline:

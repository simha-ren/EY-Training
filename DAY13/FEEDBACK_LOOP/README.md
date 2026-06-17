# FinSight AI: LLM Prompt Engineering Feedback Loop

## Overview

**FinSight AI** is an LLM prompt evaluation framework designed to test, compare, and improve prompt versions for generating **credit risk memos** in financial applications.

The project implements an automated feedback loop to identify and reduce:

- Hallucinated financial information
- Missing critical memo sections
- Incorrect output formatting
- Excessive output length
- User correction requirements

The objective is to systematically improve prompt engineering quality for regulated financial workflows.

---

# Project Goals

The notebook pipeline focuses on:

1. **Simulating LLM Performance**
   - Execute multiple prompt versions against predefined borrower profiles.
   - Compare baseline and improved prompt strategies.

2. **Automated Quality Evaluation**
   - Detect hallucinations.
   - Validate required memo sections.
   - Check output length constraints.
   - Simulate user correction feedback.

3. **Persistent Experiment Logging**
   - Store LLM requests, responses, metrics, and failures in SQLite.

4. **Prompt Version Benchmarking**
   - Compare:
     - `PROMPT_V1_0` → Baseline
     - `PROMPT_V1_1` → Structured output
     - `PROMPT_V2_0` → Guardrails + improved reasoning workflow

5. **Performance Visualization**
   - Generate failure analysis charts.
   - Compare prompt improvements visually.

---

# System Architecture

```text
+-----------------------+
|   Borrower Profiles   |
|  (Input Simulation)   |
+-----------+-----------+
            |
            v
+-----------------------+
| Prompt Configuration  |
| v1.0 / v1.1 / v2.0    |
+-----------+-----------+
            |
            v
+-----------------------+
|    LLM Call Layer     |
| API / Mock Generator  |
+-----------+-----------+
            |
            v
+-----------------------+
| Generated Risk Memo   |
+-----------+-----------+
            |
            v
+-----------------------+
|   Quality Evaluation  |
| Hallucination Checks  |
| Missing Sections      |
| Length Validation     |
+-----------+-----------+
            |
            v
+-----------------------+
|     SQLite Logs       |
| finsight_logs.db      |
+-----------+-----------+
            |
            v
+-----------------------+
| Analysis & Reporting  |
| Pandas / Matplotlib   |
| W&B Integration       |
+-----------------------+
```

---

# Pipeline Components

## 1. Borrower Profiles

A collection of simulated borrower cases:

- Clean financial profiles
- Edge cases
- Ambiguous inputs
- Adversarial scenarios

Each profile evaluates how reliably the LLM generates a credit memo.

---

## 2. Prompt Configurations

The system evaluates different prompt engineering strategies.

### PROMPT_V1_0 — Baseline

A minimal prompt without strong guardrails.

```text
System:
You are a credit analyst.
Generate a credit risk memo based on borrower data.

User:
Borrower data:
{data}

Write a credit memo.
```

### PROMPT_V1_1 — Structured Output

Introduces:

- Memo structure
- Word count limits
- Data-only generation rules

```text
Generate a credit memo for:
{data}

Use only provided information.
Do not extrapolate.
```

### PROMPT_V2_0 — Guardrails + Improved Reasoning

Designed for financial compliance workflows.

Includes:

- Numeric fact extraction
- Consistency checks
- Anti-hallucination rules
- Required memo sections

Example process:

```text
Step 1:
Identify every numeric fact.

Step 2:
Check for inconsistencies.

Step 3:
Generate memo using only verified facts.
```

---

# LLM Execution Layer

Function:

```python
call_model_with_prompt()
```

Supports:

- Live LLM API execution
- Offline deterministic mock simulation

Possible integrations:

- OpenAI API
- Groq
- Other compatible LLM providers

If API keys are unavailable, the system automatically runs in simulation mode.

---

# Quality Evaluation Framework

The pipeline evaluates generated memos using automated probes.

## Hallucination Detection

Checks whether the model creates:

- Unsupported financial numbers
- Fabricated borrower details
- Unverified claims

Metric:

```
Hallucination Rate
=
Hallucinated Outputs / Total Outputs
```

---

## Missing Section Detection

Validates presence of:

- Borrower overview
- Financial analysis
- Risk assessment
- Recommendation

Metric:

```
Missing Section Rate
=
Invalid Outputs / Total Outputs
```

---

## Output Length Validation

Checks compliance with expected memo size.

---

## User Correction Simulation

Simulates human review feedback.

Detects:

- Incorrect details
- Missing information
- Poor formatting

---

# Database Logging

All experiments are stored in:

```
finsight_logs.db
```

Each record contains:

| Field | Description |
|-|-|
| request_id | Unique execution ID |
| timestamp | Execution time |
| prompt_version | Tested prompt |
| model | LLM identifier |
| input_tokens | Input size |
| output_tokens | Output size |
| latency_ms | Generation latency |
| cost_usd | Estimated API cost |
| output_text | Generated memo |
| hallucination_flag | Quality result |
| missing_sections | Missing fields |
| failure_category | Error classification |

---

# Failure Classification

The system categorizes failures:

```text
HALLUCINATION
MISSING_SECTION
LENGTH_VIOLATION
USER_CORRECTION_OTHER
```

Implemented using:

```python
categorise_failure()
```

---

# Evaluation Metrics

Tracked metrics:

| Metric | Description |
|-|-|
| Hallucination Rate | Fabricated information frequency |
| Missing Section Rate | Missing memo components |
| User Correction Rate | Human review failures |
| Failure Rate | Overall quality failure |
| Average Latency | Response generation time |
| Average Cost | Cost per memo |
| Average Word Count | Output size |

---

# Simulation Results

Evaluation performed on:

```
10 borrower profiles
```

Comparison:

| Prompt Version | Hallucination | Missing Sections | User Correction | Failure Rate | Avg Cost |
|-|-|-|-|-|-|
| v1.0 | 40% | 100% | 60% | 100% | $0.0003 |
| v2.0 | 0% | 0% | 0% | 0% | $0.0018 |

---

# Key Findings

## Quality Improvement

Prompt `v2.0` achieved:

- 0% hallucination rate
- 0% missing sections
- 0% user corrections
- 0% overall failure rate

Compared with the baseline prompt:

- Higher compliance
- Better structure
- Improved reliability

---

## Cost Trade-off

Improved quality increased cost:

```
v1.0:
$0.0003 / memo

v2.0:
$0.0018 / memo
```

The increase comes from:

- Longer system instructions
- Additional validation steps
- More structured output generation

---

# Generated Artifacts

After execution:

## 1. SQLite Experiment Database

```
finsight_logs.db
```

Stores:

- Prompt experiments
- LLM outputs
- Quality metrics
- Failure analysis

---

## 2. Failure Analysis Chart

```
failure_analysis.png
```

Contains:

- Failure category distribution
- Output length analysis

---

## 3. Before vs After Comparison

```
before_after_comparison.png
```

Visual comparison of:

- Hallucination rate
- Missing sections
- User corrections
- Overall failures

---

# Installation

## Requirements

Python:

```
Python 3.8+
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Environment Setup

Optional API configuration:

Create:

```
.env
```

Add:

```env
OPENAI_API_KEY=your_key
GROQ_API_KEY=your_key
```

Without API keys:

- Mock LLM mode runs automatically
- Results remain reproducible

---

# Running the Project

Launch notebook:

```bash
jupyter notebook
```

Run all cells.

The main pipeline executes:

```python
main()
```

Outputs generated:

```
finsight_logs.db
failure_analysis.png
before_after_comparison.png
```

---

# Future Improvements

Potential extensions:

- Add real credit datasets
- Integrate human feedback collection
- Add LLM-as-a-Judge evaluation
- Support automated prompt optimization
- Add production monitoring dashboards
- Implement model comparison benchmarking

---

# Tech Stack

| Component | Technology |
|-|-|
| Language | Python |
| Data Processing | Pandas |
| Visualization | Matplotlib |
| Database | SQLite |
| Experiment Tracking | Weights & Biases |
| LLM Integration | OpenAI / Groq compatible APIs |

---

# License

This project is intended for research and experimentation in LLM evaluation and prompt engineering workflows.

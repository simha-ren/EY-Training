# README: Prompt Feedback Loop with Automatic Iteration (Groq Edition)

```markdown
# FinSight AI: LLM Prompt Engineering Feedback Loop

## Project Overview
This project implements a feedback loop to evaluate and compare different Large Language Model (LLM) prompt versions for generating credit risk memos. The goal is to systematically identify and mitigate issues like hallucination, missing information, and suboptimal output structures, ultimately leading to improved prompt engineering for financial applications.

## Purpose
The core purpose of this notebook is to:
1.  **Simulate LLM Performance**: Execute various prompt versions against a set of predefined borrower profiles.
2.  **Automated Quality Probing**: Programmatically assess the quality of generated LLM outputs based on defined metrics (e.g., hallucination, missing sections, length violations).
3.  **Log and Analyze Results**: Store detailed logs of each LLM call and its quality assessment in a SQLite database.
4.  **Compare Prompt Versions**: Provide a quantitative comparison between a baseline prompt (v1.0) and an improved prompt (v2.0) to demonstrate the impact of prompt engineering.
5.  **Visualize Outcomes**: Generate charts to illustrate failure distributions and comparative performance.

## Architecture Overview
The system is designed as a simulation and evaluation pipeline:

```
+-----------------------+
|   Borrower Profiles   |
| (Input Data Simulation) |
+-----------+-----------+
            |
            v
+-----------+-----------+
|  Prompt Configuration |
|  (v1.0, v1.1, v2.0)   |
+-----------+-----------+
            |
            v
+-----------------------+
|  LLM Call Mechanism   |
|  (Live API or Mock)   |
+-----------+-----------+
            |
            v
+-----------------------+
|   Generated LLM Output|
| (Credit Risk Memo Text) |
+-----------+-----------+
            |
            v
+-----------------------+
|    Quality Probes     |
| (Hallucination, Missing |
|  Sections, Length)    |
+-----------+-----------+
            |
            v
+-----------------------+
|    SQLite Database    |
|   (finsight_logs.db)  |
|     Log Storage       |
+-----------+-----------+
            |
            v
+-----------------------+
|    Analysis & Reports |
| (Pandas, Matplotlib,  |
|   WandB Integration)  |
+-----------+-----------+
            |
            v
+-----------------------+
|   Output Artifacts    |
| (PNG Charts, Metrics) |
+-----------------------+
```

### Key Components & Flow:
1.  **Borrower Profiles**: A curated list of mock borrower data, including clean, tricky, and adversarial cases, serves as input for the LLM. Each profile simulates a unique scenario for memo generation.
2.  **Prompt Configuration**: Different prompt versions (`PROMPT_V1_0`, `PROMPT_V1_1`, `PROMPT_V2_0`) are defined, each with distinct system and user instructions to guide the LLM.
3.  **LLM Call Mechanism (`call_model_with_prompt`)**: This function orchestrates the interaction with the LLM. It can either make live API calls (e.g., Groq, xAI) if API keys are configured, or fall back to a deterministic mock generator for consistent testing and offline execution.
4.  **Quality Probes**: A suite of functions (`probe_hallucination`, `probe_missing_sections`, `probe_output_length`, `simulate_user_correction`) automatically analyzes the LLM's output against predefined quality criteria. This includes checking for fabricated numbers, absent critical sections, and word count adherence.
5.  **SQLite Database (`finsight_logs.db`)**: All LLM interactions, including input prompts, generated outputs, latency, cost, and quality probe results, are meticulously logged in a local SQLite database for persistent storage and later analysis.
6.  **Analysis & Reporting**: Pandas DataFrames are used to read and process the logs from the SQLite database. Matplotlib is employed for data visualization, creating charts that highlight performance differences. Integration with Weights & Biases (W&B) is available for advanced experiment tracking and hyperparameter sweeps.
7.  **Failure Triage (`categorise_failure`)**: A function categorizes different types of failures (e.g., 'HALLUCINATION', 'MISSING_SECTION', 'LENGTH_VIOLATION', 'USER_CORRECTION_OTHER') for a detailed breakdown of issues.

## Prompt Versions Evaluated

### `PROMPT_V1_0` (Baseline)
*   **Description**: A minimal, straightforward prompt, simulating a basic request without specific guardrails or formatting instructions. Prone to common LLM issues.
*   **System**: `You are a credit analyst. Generate a credit risk memo based on the borrower data.`
*   **User Template**: `Borrower data:
{data}

Write a credit memo.`

### `PROMPT_V1_1` (Structured Output)
*   **Description**: Introduces instructions for structured output and length constraints, aiming to improve memo format.
*   **System**: `You are a credit analyst AI at FinSight AI. Generate a credit risk memo (150-250 words) structured as: ... Use only the data provided. Do not extrapolate or add information not given.`
*   **User Template**: `Generate a credit memo for:
{data}`

### `PROMPT_V2_0` (Improved: Chain-of-Thought + Guardrails)
*   **Description**: Incorporates a chain-of-thought process and explicit anti-hallucination and formatting guardrails, designed to produce highly compliant and accurate outputs for regulated environments.
*   **System**: `You are a senior credit analyst at FinSight AI... PROCESS: Step 1: List every numeric fact... Step 2: Identify inconsistencies... Step 3: Write the credit memo using ONLY those stated facts. MEMO FORMAT: ... COMPLIANCE RULES: ...`
*   **User Template**: `Generate a credit memo for the following borrower.

BORROWER DATA:
{data}`

## Evaluation Metrics
The simulation tracks and evaluates performance based on:
*   **Hallucination Rate**: Percentage of memos containing fabricated or unverified numerical information.
*   **Missing Sections Rate**: Percentage of memos lacking essential sections (e.g., 'borrower', 'financial', 'risk', 'recommend').
*   **User Correction Rate**: Simulated rate of user feedback indicating an issue with the memo.
*   **Overall Failure Rate**: Composite rate indicating any identified issue (hallucination, missing sections, length violation, or user correction).
*   **Average Latency (ms)**: Time taken for the LLM to generate a response.
*   **Average Cost/Memo (USD)**: Estimated monetary cost per generated memo based on token usage.
*   **Average Word Count**: The average length of the generated memos.

## Simulation Results (v1.0 vs v2.0)

After running the simulation with 10 borrower profiles, the comparison between `v1.0 (Baseline)` and `v2.0 (Improved)` is as follows:

| prompt_version | hallucin_rate | missing_sec_rate | user_correction | failure_rate | avg_cost |
|:---------------|:--------------|:-----------------|:----------------|:-------------|:---------|
| v1.0           | 0.4           | 1.0              | 0.6             | 1.0          | 0.0003   |
| v2.0           | 0.0           | 0.0              | 0.0             | 0.0          | 0.0018   |

### Key Findings:
*   **Significant Quality Improvement**: Prompt `v2.0` dramatically reduced hallucination, missing sections, user corrections, and overall failure rates to 0% compared to `v1.0`.
*   **Cost Trade-off**: The enhanced quality of `v2.0` comes at a higher average cost per memo (from $0.0003 for v1.0 to $0.0018 for v2.0), likely due to more complex instructions leading to higher token usage.

## Output Files
The execution of the notebook generates the following output files:

1.  **`finsight_logs.db`**
    *   **Description**: A SQLite database file containing all structured logs from the LLM simulation. Each entry includes details like `request_id`, `timestamp`, `prompt_version`, `model`, `input_tokens`, `output_tokens`, `latency_ms`, `cost_usd`, `output_text`, and various quality probe results (`hallucination_flag`, `missing_sections`, `user_correction`, `failure_category`).
    *   **Purpose**: Provides a persistent, queryable record of every LLM interaction and its assessed quality, enabling detailed historical analysis and auditing.

2.  **`failure_analysis.png`**
    *   **Description**: A Matplotlib generated image file visualizing the failure distribution for the `v1.0 (Baseline)` prompt. It typically shows a bar chart of failure categories (e.g., Hallucination, Missing Section) and a histogram of output word counts.
    *   **Purpose**: Helps to quickly identify the prevalent types of issues with the baseline prompt and understand output length characteristics.

3.  **`before_after_comparison.png`**
    *   **Description**: A Matplotlib generated image file providing a side-by-side bar chart comparison of key quality metrics (Hallucination Rate, Missing Sections, User Corrections, Overall Failure Rate) between `v1.0` and `v2.0` prompts.
    *   **Purpose**: Offers a clear, visual summary of the improvements achieved by the `v2.0` prompt over the `v1.0` baseline, making it easy to convey the impact of prompt engineering efforts.

## How to Run
To execute this simulation and generate the reports:
1.  **Environment Setup**: Ensure Python (3.8+) and `pip` are installed.
2.  **Install Dependencies**: Install necessary libraries using `pip install -r requirements.txt` (assuming a `requirements.txt` is created from the imports).
3.  **API Keys (Optional)**: If you wish to use live LLM APIs, set `GROQ_API_KEY` (for Groq/xAI) or `OPENAI_API_KEY` in a `.env` file in the project root. If keys are not set, the simulation will run in mock mode.
4.  **Execute the Notebook**: Run all cells in the Jupyter/Colab notebook sequentially. The `main()` function handles the full simulation pipeline.
5.  **Review Outputs**: Check the generated `.db` and `.png` files in the working directory for detailed logs and visualizations.

```

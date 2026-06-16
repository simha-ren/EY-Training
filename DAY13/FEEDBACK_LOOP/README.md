# README: Prompt Feedback Loop with Automatic Iteration (Groq Edition)

## Project Overview

This lab focuses on establishing a robust prompt feedback loop for AI credit risk assessment, specifically using FinSight AI's LLaMA 3.3 70B model deployed on Groq. The primary goal is to instrument LLM calls for structured logging, build automated quality probes, identify and triage failure patterns, and iteratively revise prompts to achieve measurable improvements in credit memo generation.

### Key Objectives:

*   **Structured Logging:** Instrument LLM calls to log detailed metadata and outputs to a persistent SQLite database.
*   **Automated Quality Probes:** Develop and apply probes to automatically detect common failure modes like hallucinations, missing sections, and output length violations.
*   **Failure Triage:** Analyze failure patterns to understand the root causes and prioritize prompt improvements.
*   **Prompt Iteration:** Revise prompts based on empirical evidence to enhance LLM performance.
*   **Measurable Improvement:** Quantify the impact of prompt revisions through before/after comparisons of key metrics.
*   **LangSmith Integration:** Implement LangSmith tracing for comprehensive visibility into LLM operations.

## Setup and Dependencies

This notebook uses several Python libraries for LLM interaction, data handling, and visualization.

### Prerequisites:

*   **Groq API Key:** Obtain a `GROQ_API_KEY` from Groq and store it in Colab's `userdata` secrets manager.
*   **LangChain API Key (Optional but Recommended):** For LangSmith tracing, obtain a `LANGCHAIN_API_KEY` from LangSmith and store it in Colab's `userdata` secrets manager.

### Installation:

The following command installs all necessary dependencies:

```python
!pip install groq bert-score pandas matplotlib seaborn numpy scikit-learn tqdm langsmith langchain-groq -q
```

### Environment Variables:

*   `GROQ_API_KEY`: Your API key for accessing Groq models.
*   `LANGCHAIN_TRACING_V2`: Set to `'true'` to enable LangSmith tracing.
*   `LANGCHAIN_API_KEY`: Your API key for LangSmith.
*   `LANGCHAIN_PROJECT`: Defines the project name in LangSmith (e.g., `'finsight-feedback-loop-groq'`)

## Methodology

1.  **Logging Schema & Database Initialization:** A `LLMLogEntry` dataclass defines the structured logging format, and an SQLite database (`finsight_logs_groq.db`) is initialized to store all LLM call data.
2.  **Prompt Variants:** Three prompt versions are defined:
    *   `v1.0`: Baseline, minimal prompt.
    *   `v1.1`: Structured output prompt.
    *   `v2.0`: Chain-of-thought with anti-hallucination guardrails.
3.  **LLM Call Function:** A `traced_call_model_with_prompt` function is implemented using `langchain-groq` and `langsmith`'s `@traceable` decorator, ensuring all LLM interactions are automatically traced and logged.
4.  **Simulation Runs:** 50 `BORROWER_PROFILES` are used to simulate production requests. Initial runs were conducted with `v1.0` and `v2.0` prompts. (Note: `SIMULATE_N` was set to 10 for faster execution in the demo.)
5.  **Automated Quality Probes:** Functions like `probe_hallucination`, `probe_missing_sections`, `probe_output_length`, and `simulate_user_correction` are applied to the generated LLM outputs. These probes categorize potential failures.
6.  **Failure Triage:** Logs are analyzed to identify the frequency and types of failures across different prompt versions.
7.  **Comparison Dashboard:** A dashboard is generated to compare key metrics (failure rates, latency, cost, etc.) between prompt versions `v1.0` and `v2.0`.

## Key Findings (Based on current simulation results)

*   **Failure Rate:** The `v2.0` prompt (CoT with anti-hallucination) exhibited a significantly higher failure rate (100%) compared to `v1.0` (0%) in the limited simulation. This is contrary to expectation and indicates that the probes are likely flagging `v2.0`'s highly structured output requirements as failures, or that `v2.0` is generating responses that are considered 'missing sections' despite its detailed instructions.
*   **Latency:** `v2.0` showed a slight average latency improvement of approximately `6.16 ms` over `v1.0` (115.70 ms for v1.0 vs. 109.55 ms for v2.0). This suggests that despite being a more complex prompt, `v2.0` might be processed efficiently by the Groq model.
*   **Cost:** Both `v1.0` and `v2.0` showed `0.0` average cost. This implies that the token counts might not have been correctly calculated or logged, potentially due to API errors in earlier runs, or that the `SIMULATE_N` was too small to register a meaningful cost.
*   **Hallucination:** Both `v1.0` and `v2.0` currently show a `0.0` hallucination rate, which might be an anomaly given the expected behavior of a baseline prompt. Further investigation into the `probe_hallucination` logic or increased simulation size is warranted.

## How to Run the Notebook

1.  **Open in Colab:** Ensure you are running this notebook in Google Colab.
2.  **Set up API Keys:**
    *   Go to 'Secrets' (key icon on the left panel).
    *   Add `GROQ_API_KEY` and `LANGCHAIN_API_KEY` with your respective keys.
3.  **Run All Cells:** Execute all cells in sequential order. Some cells are designed to be re-run after modifications or to refresh data. The `SIMULATE_N` variable can be adjusted to run more comprehensive simulations (e.g., set to 50 for the full set of borrower profiles).
4.  **Review Outputs:** Examine the printed output, generated plots, and the LangSmith UI for detailed traces.

## Future Work / Next Steps

*   **Investigate `v2.0` Failure Rate:** Deep dive into why `v2.0` is flagging such a high failure rate. Adjust probes if they are too strict for the intended `v2.0` output or refine the prompt further.
*   **Verify Token Counts and Cost:** Ensure accurate token counting and cost calculation in the `traced_call_model_with_prompt` function and database logging.
*   **Increase Simulation Size:** Run simulations with `SIMULATE_N = 50` (or more) to get a more statistically significant comparison of performance metrics.
*   **Refine Probes:** Continuously improve the quality probes based on real-world feedback and deeper analysis of LLM outputs.
*   **Advanced LangSmith Analysis:** Utilize LangSmith's features to compare traces, identify bottlenecks, and evaluate prompt effectiveness more deeply.
*   **Prompt Optimization:** Conduct further prompt engineering experiments, potentially incorporating few-shot examples or more sophisticated anti-hallucination techniques.

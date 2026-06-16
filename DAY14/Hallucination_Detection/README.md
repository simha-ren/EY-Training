# Hallucination Detection with OpenAI GPT API

This notebook provides a framework for detecting various types of hallucinations in LLM-generated answers, using the OpenAI GPT API.

## Features:

-   **Intrinsic Hallucination**: Detects contradictions with the source context.
-   **Extrinsic Hallucination**: Identifies unsupported facts added to the answer.
-   **Closed-domain Violation**: Flags answers that go outside the allowed scope.
-   **Factuality Drift**: Checks for outdated or false facts.
-   **Cascading Hallucination**: Recognizes errors propagating from previous conversation turns.
-   **FactScore-like Precision**: Measures the ratio of supported factual claims.
-   **RAG Groundedness Score**: Evaluates how well claims are supported by retrieved chunks.
-   **SelfCheckGPT-like Consistency**: Assesses consistency across multiple generated samples.

## Setup:

1.  **Install dependencies**:

    ```bash
    !pip install openai pydantic python-dotenv
    ```

2.  **OpenAI API Key**: Set your `OPENAI_API_KEY` in Colab secrets. Click on the '🔑 Secrets' icon in the left sidebar, add a new secret named `OPENAI_API_KEY`, and paste your OpenAI API key as the value. Ensure 'Notebook access' is enabled.

## Usage:

The `detect_hallucination` function can be used to analyze an LLM's answer against a given source context, question, and other parameters. The example usage is provided in the `if __name__ == '__main__':` block.

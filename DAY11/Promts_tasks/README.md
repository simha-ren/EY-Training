# Prompt Core Tasks

## Introduction
This notebook demonstrates a set of core NLP tasks, including earnings call summarization and support ticket classification, utilizing the Gemini API via an OpenAI-compatible endpoint. It incorporates prompt engineering techniques like zero-shot and few-shot learning, along with logging and evaluation metrics.

## Features
- **Earnings Call Summarization**: Summarizes financial snippets using both zero-shot and few-shot prompting.
- **Support Ticket Classification**: Categorizes customer support tickets into predefined categories with reasoning.
- **Gemini API Integration**: Leverages Google's Gemini API for advanced NLP capabilities.
- **OpenAI SDK Compatibility**: Utilizes the OpenAI Python SDK by routing requests to Gemini's OpenAI-compatible endpoint.
- **Prompt Logging**: Records all prompts and responses for analysis and debugging.
- **ROUGE-L Scoring**: Evaluates the quality of summarization tasks against reference summaries.
- **Argparse for flexible execution**: Supports running the script in mock mode for offline testing or with the actual Gemini API.
- **Colab Secrets Integration**: Securely retrieves the Gemini API key from Colab's secrets manager.

## Setup
### 1. API Key Configuration
To use the Gemini API, you need an API key. Please follow these steps to set it up:
1.  Go to [Google AI Studio](https://ai.google.dev/) to create your Gemini API key.
2.  In Google Colab, open the "Secrets" tab (🔑 icon on the left panel).
3.  Add a new secret with the name `GEMINI_API_KEY` and paste your API key as the value.

### 2. Install Dependencies
Ensure you have the necessary libraries installed. If running in a fresh Colab environment, you might need to install `openai` and `langchain-core`:

```python
!pip install openai langchain-core
```

## Usage
The main script can be run to perform the summarization and classification tasks. It can operate in two modes: 

### Running with Gemini API (Live Mode)
By default, the script attempts to use the configured Gemini API key. Ensure your `GEMINI_API_KEY` is correctly set in Colab secrets.

To run the script in live mode, ensure the `parse_args()` function is configured to *not* include `--mock` in the arguments passed to `parser.parse_args()`:

```python
# In the parse_args() function:
args = parser.parse_args([]) # For live mode
# or, if you want to explicitly pass an empty list when running in Colab:
# import sys
# if 'ipykernel_launcher.py' in sys.argv[0]:
#    args = parser.parse_args([])
# else:
#    args = parser.parse_args()
```

### Running in Mock Mode (Offline Testing)
If you want to test the script's logic without consuming your API quota or if the API is temporarily unavailable, you can run it in mock mode. In this mode, pre-defined mock responses are used instead of making actual API calls.

To run the script in mock mode, ensure the `parse_args()` function is configured to include `--mock` in the arguments:

```python
# In the parse_args() function:
args = parser.parse_args(['--mock']) # For mock mode
```

After setting the desired mode, simply run the cell containing the `main()` function.

## Output
Upon successful execution, the script generates the following files in the `output/` directory:
- `summarisation_results.csv`: Contains the results of the earnings call summarization, including zero-shot, few-shot, and reference summaries, along with ROUGE-L scores.
- `ticket_classifier_results.csv`: Contains the results of the support ticket classification, showing the original ticket, ground truth, predicted category, reasoning, and correctness flag.
- `promptlayer_log.jsonl`: A line-delimited JSON file logging all API prompts and responses.
- `task3_report.json`: A summary report of the tasks completed, model used, average ROUGE-L F1 score, and ticket classifier accuracy.

## Code Structure
- `EARNINGS_CALL_SNIPPETS`: Sample data for summarization tasks.
- `TICKETS`: Sample data for ticket classification tasks.
- `PromptLogRecord`, `PromptLayerLogger`: Classes for local logging of prompts and responses.
- `create_client()`: Initializes the OpenAI client to connect to the Gemini API endpoint.
- `call_gemini()`: Handles API calls to Gemini, including retry logic for rate limits.
- `create_zero_shot_summary_prompt()`, `create_few_shot_summary_prompt()`: Define LangChain prompt templates for summarization.
- `create_ticket_classifier_prompt()`: Defines the prompt template for ticket classification.
- `run_summarisation_chain()`, `run_ticket_classifier()`: Orchestrate the respective NLP tasks.
- `parse_classifier_response()`: Parses the JSON response from the ticket classifier.
- `rouge_l_score()`, `tokenize()`, `longest_common_subsequence_length()`: Functions for calculating ROUGE-L scores.
- `mock_response()`: Provides simulated API responses for mock mode.
- `save_summarisation_results()`, `save_classifier_results()`, `save_report()`: Functions for saving the generated output files.
- `parse_args()`: Parses command-line arguments to control script behavior.
- `main()`: The entry point of the script, orchestrating the overall workflow.

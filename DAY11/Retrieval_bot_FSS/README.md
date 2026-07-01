# RAG System with LangChain and FAISS for Policy Document Q&A

This notebook implements a Retrieval-Augmented Generation (RAG) system designed to answer questions based on a provided PDF policy document. It leverages LangChain for orchestration, FAISS for efficient vector storage and retrieval, and can optionally use the Google Gemini API for powerful language model capabilities.

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Setup](#setup)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [API Key Configuration](#api-key-configuration)
  - [PDF Document](#pdf-document)
- [File Structure](#file-structure)
- [Usage](#usage)
  - [Running the RAG Chain](#running-the-rag-chain)
  - [Asking Multiple Questions](#asking-multiple-questions)
- [Core Components](#core-components)
- [Troubleshooting](#troubleshooting)
- [Future Enhancements](#future-enhancements)

## Introduction

This project provides a robust framework for building a RAG system. It allows you to: 
- Load and process PDF documents.
- Create vector embeddings of the document content.
- Store embeddings in a FAISS index for fast semantic search.
- Retrieve relevant document chunks based on a user query.
- Generate coherent answers using a large language model (LLM), incorporating the retrieved context.

This is particularly useful for querying large documents like policy manuals, research papers, or legal texts, where finding specific information quickly is crucial.

## Features

*   **PDF Document Ingestion:** Easily load text from PDF files.
*   **Text Chunking:** Splits documents into manageable chunks for effective embedding.
*   **FAISS Vectorstore:** Utilizes FAISS for high-performance similarity search.
*   **Flexible Embeddings:** Supports both a mock `LocalHashEmbeddings` for offline testing and `OpenAIEmbeddings` (compatible with Gemini API) for production use.
*   **LangChain Integration:** Uses LangChain's powerful abstractions for building the RAG chain.
*   **Gemini API Compatibility:** Seamlessly integrates with the Gemini API for generative capabilities.
*   **Mock Mode:** Allows for testing the retrieval pipeline without needing an active API key.

## Setup

### Prerequisites

*   Google Colab environment (recommended) or a local Python environment.
*   Python 3.8+

### Installation

Run the following `pip install` commands in the provided cells to set up the necessary libraries:

```python
# Install necessary libraries
!pip install -qqq langchain==0.2.10 langchain-community==0.2.9 langchain-openai==0.1.15 pypdf
!pip install -qqq faiss-cpu # Separate installation for faiss-cpu
!pip install -qqq reportlab # For creating dummy PDF
```

### API Key Configuration

To use the actual Google Gemini API (instead of the mock mode), you need to provide your API key:

1.  **Obtain API Key:** If you don't have one, create a Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
2.  **Colab Secrets:** In your Colab notebook, go to the left-hand panel, click on the "🔑 Secrets" icon.
3.  **Add Secret:** Add a new secret with the name `GEMINI_API_KEY` and paste your API key as its value.

The notebook automatically retrieves this key using `from google.colab import userdata`.

### PDF Document

The system requires a PDF document to operate on.

*   **Dummy PDF:** The notebook includes a `create_dummy_pdf` function that generates a sample `policy_document.pdf` in the `/content` directory. This is useful for initial testing.
*   **Your Own PDF:** To use your own PDF, upload it to the Colab environment (e.g., to `/content/your_document.pdf`) and modify the `PDF_PATH` variable in the script or pass it via the `--pdf` argument.

## File Structure

*   `/content/policy_document.pdf`: The default PDF file used by the RAG system.
*   The Python code for the RAG chain (`create_policy_qa_chain`, `main`, etc.) is defined within the notebook itself, primarily in the cell with ID `bca07be0`.

## Usage

### Running the RAG Chain

The core logic for the RAG system is encapsulated in the `main()` function within the `bca07be0` cell. You can execute this function by setting the `sys.argv` list, which mimics command-line arguments.

**Arguments:**

*   `--pdf [PATH]`: Specifies the path to the PDF document. (Default: `/content/policy_document.pdf`)
*   `--question "[YOUR QUESTION]"`: The question you want the RAG system to answer.
*   `--mock`: (Optional flag) If present, the system will use `LocalHashEmbeddings` and `LocalPolicyQAChain` for offline testing, bypassing the Gemini API. Remove this flag to engage the actual Gemini API (requires `GEMINI_API_KEY`).

**Example (initial run):**

```python
import sys

# Temporarily modify sys.argv to pass the arguments to parse_args()
sys.argv = [
    'your_script_name.py', 
    '--pdf', str(BASE_DIR / 'policy_document.pdf'), 
    '--question', 'What is the policy regarding remote work reimbursement?', 
    '--mock'
]

try:
    main() # Call the main function of the script
except (FileNotFoundError, ValueError, APIStatusError) as exc:
    print(f"Error: {exc}")
```

### Asking Multiple Questions

The notebook demonstrates how to iterate through a list of questions and run the RAG chain for each:

```python
new_questions = [
    "What are the eligibility criteria for the remote work stipend?",
    "How long do I have to submit reimbursement requests for travel expenses?",
    "What kind of expenses does the remote work stipend cover?"
]

for i, question in enumerate(new_questions):
    print(f"\n--- Running RAG for Question {i+1} ---")
    print(f"Question: {question}")
    # Update sys.argv to pass the new question
    sys.argv = ['your_script_name.py', '--pdf', str(BASE_DIR / 'policy_document.pdf'), '--question', question, '--mock']
    try:
        main()
    except (FileNotFoundError, ValueError, APIStatusError) as exc:
        print(f

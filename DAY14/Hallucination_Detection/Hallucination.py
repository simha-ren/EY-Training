import json
import os
from typing import List, Literal, Optional

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field
from google.colab import userdata # Import userdata for Colab secrets


# SCRIPT_DIR = os.path.dirname(__file__) # __file__ is not defined in Colab
# SCRIPT_DIR = "/content" # Assuming .env is in the root content directory in Colab
# load_dotenv(os.path.join(SCRIPT_DIR, ".env"), override=True) # Not needed if using Colab secrets for API key

# Retrieve API key from Colab secrets
OPENAI_API_KEY = userdata.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not found in Colab secrets. Please set it up as instructed.")

client = OpenAI(api_key=OPENAI_API_KEY)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini") # MODEL can still be loaded from environment or .env if present


class ClaimCheck(BaseModel):
    claim: str
    status: Literal["supported", "contradicted", "unsupported", "out_of_scope", "possibly_outdated"]
    hallucination_type: Literal["none", "intrinsic", "extrinsic", "closed_domain", "factuality_drift", "cascading"]
    evidence_from_context: Optional[str] = None
    explanation: str
    confidence: float = Field(ge=0, le=1)


class HallucinationReport(BaseModel):
    total_claims: int
    supported_claims: int
    contradicted_claims: int
    unsupported_claims: int
    out_of_scope_claims: int
    possibly_outdated_claims: int
    factscore_like_precision: float = Field(ge=0, le=1)
    rag_groundedness_score: float = Field(ge=0, le=1)
    selfcheck_consistency_score: float = Field(ge=0, le=1)
    overall_hallucination_risk: Literal["low", "medium", "high"]
    claim_checks: List[ClaimCheck]
    final_verdict: str
    safer_answer: Optional[str] = None


def generate_selfcheck_samples(question: str, source_context: str, n: int = 3) -> List[str]:
    samples = []
    for _ in range(n):
        response = client.responses.create(
            model=MODEL,
            input=[
                {
                    "role": "system",
                    "content": "Answer only using the given source context. If the answer is not present, say you don't know.",
                },
                {"role": "user", "content": f"Question:\n{question}\n\nSource context:\n{source_context}"},
            ],
            temperature=0.7,
        )
        samples.append(response.output_text)
    return samples


def detect_hallucination(
    question: str,
    answer: str,
    source_context: str,
    allowed_scope: str = "Only answer from the provided source context.",
    previous_turns: Optional[str] = None,
    gold_reference_answer: Optional[str] = None,
    selfcheck_samples: Optional[List[str]] = None,
) -> HallucinationReport:
    previous_turns = previous_turns or "No previous turns provided."
    gold_reference_answer = gold_reference_answer or "No gold reference answer provided."
    selfcheck_samples = selfcheck_samples or []

    prompt = f"""
You are a hallucination detection evaluator.

Evaluate the candidate answer against the source context.

Definitions:
- Intrinsic hallucination: answer contradicts the source context.
- Extrinsic hallucination: answer adds plausible but unsupported facts.
- Closed-domain hallucination: answer goes outside allowed scope.
- Factuality drift: answer uses outdated or false facts compared to trusted context.
- Cascading hallucination: answer continues an earlier mistake from previous conversation turns.
- FactScore-like precision: supported factual claims / total factual claims.
- RAG groundedness score: how many answer claims are grounded in source context.
- SelfCheckGPT-like consistency: whether answer is consistent with other generated samples.

Important rules:
1. Do not use hidden reasoning in output.
2. Break the answer into factual claims.
3. For every claim, classify it.
4. Use only source context, previous turns, gold reference, and samples.
5. If evidence is missing, mark unsupported.
6. If answer contradicts context, mark intrinsic.
7. If answer goes outside allowed scope, mark closed_domain.
8. If earlier conversation contains a wrong assumption repeated by answer, mark cascading.
9. Return a safer corrected answer if hallucination risk is medium or high.

Question:
{question}

Candidate answer:
{answer}

Source context:
{source_context}

Allowed scope:
{allowed_scope}

Previous conversation turns:
{previous_turns}

Gold reference answer:
{gold_reference_answer}

SelfCheck samples:
{json.dumps(selfcheck_samples, indent=2)}
"""

    response = client.responses.parse(
        model=MODEL,
        input=[
            {"role": "system", "content": "You are a strict factuality and hallucination evaluator."},
            {"role": "user", "content": prompt},
        ],
        text_format=HallucinationReport,
        temperature=0,
    )
    return response.output_parsed


if __name__ == "__main__":
    source_context = """
    Azure AI Search supports keyword search, vector search, and hybrid search.
    Hybrid search combines BM25 keyword search with vector similarity search.
    Larger chunks can include more context, but they may reduce retrieval precision.
    Smaller chunks can improve precision, but may lose surrounding context.
    """
    question = "What is hybrid search and what is the problem with large chunks?"
    answer = """
    Hybrid search combines keyword search and vector search.
    Large chunks are always better because they give more context and never reduce accuracy.
    Azure AI Search also automatically trains your LLM model.
    """
    samples = generate_selfcheck_samples(question=question, source_context=source_context, n=3)
    report = detect_hallucination(
        question=question,
        answer=answer,
        source_context=source_context,
        allowed_scope="Only answer about Azure AI Search hybrid search and chunking from the provided context.",
        selfcheck_samples=samples,
    )
    print(json.dumps(report.model_dump(), indent=2))

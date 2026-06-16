# Latency Variation Analysis using BLEU, ROUGE, and Faithfulness

## Main Observation

From the latency waterfall chart, the main cause of latency variation is the **Claude answer generation stage**, not embedding or Azure retrieval.

- **Embedding query time** is small and mostly stable across all queries.
- **Azure retrieval time** is also small and shows minimal variation.
- The major latency differences are caused by **Claude generation time**.

Queries such as **Q3, Q6, and Q7** show higher latency because Claude takes significantly longer to generate the final response.

Queries such as **Q1 and Q2** show lower latency because Claude generation time is shorter.

---

# Metrics Used for Evaluation

To determine whether additional generation time improves response quality, we evaluate answers using **BLEU**, **ROUGE**, and **Faithfulness**.

| Metric | What it checks | Meaning in latency analysis |
|---|---|---|
| **BLEU** | Word and phrase overlap with the reference answer | Higher BLEU indicates the generated answer is closer to the expected response |
| **ROUGE** | Recall-based overlap with the reference answer | Higher ROUGE indicates better coverage of important information from the expected answer |
| **Faithfulness** | Whether the answer is supported by retrieved context | Higher faithfulness indicates stronger grounding and lower hallucination risk |

---

# Metric-Based Interpretation

A high-latency query should be evaluated together with answer quality metrics.

## Case 1: High Latency + High Quality Scores

If a high-latency query has:

- High **BLEU**
- High **ROUGE**
- High **Faithfulness**

then the additional latency is justified.

This means Claude is spending more time but producing:

- More complete answers
- Better alignment with expected responses
- More grounded and reliable outputs

---

## Case 2: High Latency + Low Quality Scores

If a high-latency query has:

- Low **BLEU**
- Low **ROUGE**
- Low **Faithfulness**

then the generation process is inefficient.

Claude is consuming additional time without improving answer quality.

---

# Final Conclusion

The primary root cause of latency variation is:

> **Claude generation time**, mainly influenced by:
>
> - Answer length
> - Query complexity
> - Retrieved context size
> - Reasoning required by the model

Embedding and Azure retrieval contribute very little to overall latency variation because their execution times remain relatively stable.

---

# Optimization Recommendations

Focus optimization efforts on the generation stage:

- Reduce prompt size and unnecessary retrieved context.
- Limit unnecessarily long responses.
- Improve chunk retrieval quality.
- Provide only the most relevant context to Claude.
- Avoid prompts that encourage unnecessary reasoning or excessive verbosity.

---

# Final Decision

> If high-latency responses achieve strong BLEU, ROUGE, and Faithfulness scores, the latency is justified because it improves answer quality.
>
> If those scores are weak, the Claude generation stage should be optimized because it adds cost and delay without delivering better results.

# Day 13 Task 2: RAG Metrics and Latency Evaluation

This task evaluates each query using token count, latency, answer relevance, faithfulness, and context precision.

## Metrics

| Metric | Meaning |
| --- | --- |
| Token count | Total prompt/context plus generated answer tokens |
| Latency | Embedding, retrieval, generation, and total latency in milliseconds |
| Answer relevance | Similarity between the query and generated answer |
| Faithfulness | Share of answer terms supported by retrieved context |
| Context precision | Share of retrieved chunks relevant to the expected answer/context |

## Final Summary

- Average total tokens: 186.00
- Average total latency ms: 32.74
- Average answer relevance: 0.399
- Average faithfulness: 1.000
- Average context precision: 0.500

## Output Graphs

- `plots/all_queries_summary.png`
- `plots/q1_metrics.png`
- `plots/q2_metrics.png`
- `plots/q3_metrics.png`
- `plots/q4_metrics.png`
- `plots/q5_metrics.png`
- `plots/q6_metrics.png`

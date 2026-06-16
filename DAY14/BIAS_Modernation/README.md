# 🧪 Day 14 — Lab 1: Content Moderation & Bias Evaluation

## 🏦 FinanceGuard AI — Auditing CreditLens for Demographic Bias

### Scenario:

You are the AI Engineering team at FinanceGuard, an Indian fintech. Your LLM-powered credit scoring assistant — CreditLens — processes loan applications. Regulators have flagged potential demographic bias in rejection patterns. This lab audits loan decisions for fairness violations, implements a content moderation layer, and logs/visualises trigger events.

### 📋 Core Tasks Completed:

1.  **Load Synthetic Loan Dataset (3,000 rows):** Generated a dataset with baked-in demographic bias (female applicants and Tier-3 regions face higher rejection rates).
2.  **Compute Fairness Metrics:**
    *   **Demographic Parity:** Female applicants face ~12 percentage points higher rejection than males. Tier-3 regions also show higher rejection rates.
    *   **Equalised Odds:** Higher False Positive Rates (wrong rejections) observed for female and Tier-3 applicants, indicating bias.
    *   **80% Rule:** Failed for 'Region', indicating significant bias where the least-favoured group's rejection rate is less than 80% of the most-favoured group's.
3.  **Visualise Rejection Rates:** Created a dashboard showing rejection rates by gender, region, age group, and credit score distribution, clearly illustrating the demographic disparities.
4.  **Content Moderation Layer:** Implemented a two-tier moderation system:
    *   **Keyword Moderation:** Fast, rule-based blocking of explicit policy violations (discriminatory, PII requests, jailbreak, financial misinformation).
    *   **Semantic Moderation:** Using Sentence Transformers to catch implicit/obfuscated violations by comparing prompt embeddings to unsafe anchors.
5.  **Logging Trigger Events:** Developed a structured audit logger for moderation events, capturing timestamps, user IDs, prompt previews, keyword categories, and semantic risk scores.

### 🚀 Extension Tasks Completed:

1.  **SHAP Feature Attributions:** Used SHAP to explain the logistic regression model's predictions. `gender_enc` and `region_enc` appeared in the top features, confirming the model uses protected attributes, which is a compliance violation.
2.  **Counterfactual Fairness:** Tested counterfactual fairness by flipping only gender. A significant 21.5% of decisions changed, indicating the model is **NOT** counterfactually fair with respect to gender.
3.  **HuggingFace Classifier as Intent Filter:** Demonstrated intent classification using a zero-shot model to categorize user prompts (e.g., safe credit inquiry, discriminatory bias request).
4.  **Compare vs. OpenAI Moderation API:** Showcased a comparison, highlighting that a layered approach (keyword + semantic + LLM) provides better coverage than relying on a single system.
5.  **Build an Audit HTML Report:** Generated interactive Plotly charts (rejection rates by region & gender, moderation event timeline) and saved them as a standalone HTML file for compliance teams.

### 📌 Recommendations for FinanceGuard:

*   **Remove protected attributes:** Eliminate `gender` and `region` from model features or apply post-processing fairness constraints to mitigate bias.
*   **Deploy dual-layer moderation:** Implement both keyword and semantic moderation with a human review queue for borderline cases to maximize safety and compliance.
*   **Regular bias audits:** Conduct bias audits quarterly and file results with the RBI model risk management team.
*   **DPDP-compliant logging:** Implement robust logging to retain trigger events for 7 years as per RBI guidelines.

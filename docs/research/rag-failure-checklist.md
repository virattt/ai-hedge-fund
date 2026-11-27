# RAG / Reasoning Failure Checklist for AI Hedge Fund Research

When using LLMs to support research, strategy explanation, and risk analysis in an AI-driven hedge fund, several failure modes can undermine reliability. This checklist helps identify and categorize these issues during pipeline runs, research notebooks, and strategy post-mortems.

## Common Failure Modes

### 1. Hallucination & Chunk Drift
- **Symptom**: Narratives sound plausible but ignore part of the data
- **Example**: Model generates company analysis using outdated earnings data
- **Check**: Does every claim trace back to retrieved source?

### 2. Interpretation Collapse
- **Symptom**: Confusion between similar tickers or time windows
- **Example**: AAPL (Apple) vs AAPL (Aperam) confusion in European markets
- **Check**: Are tickers normalized to single identifier system (ISIN, CUSIP)?

### 3. Long Reasoning Chain Degradation
- **Symptom**: Long explanations drift away from original hypothesis
- **Example**: Multi-step analysis loses track of initial thesis by conclusion
- **Check**: Can you summarize the analysis in 3 sentences that match the original question?

### 4. Overconfident Bluffing
- **Symptom**: Model presents uncertain information with high confidence
- **Example**: Strong "BUY" recommendation without clear evidence
- **Check**: Are confidence levels and data sources explicitly stated?

### 5. Black-Box Debugging Difficulty
- **Symptom**: Hard to determine if bad suggestion is from retrieval, reasoning, or tools
- **Example**: Poor trade recommendation with unclear failure point
- **Check**: Is there a trace log showing retrieval → reasoning → output?

### 6. Temporal Misalignment
- **Symptom**: Analysis uses data from wrong time period
- **Example**: Using Q2 data for Q4 earnings analysis
- **Check**: Are all timestamps validated before analysis?

### 7. Context Window Saturation
- **Symptom**: Important information truncated in long documents
- **Example**: Key risk factors cut off in 10-K summary
- **Check**: Is critical information in first/last N tokens?

### 8. Retrieval-Generation Disconnect
- **Symptom**: Generated output contradicts retrieved context
- **Example**: Summary says "revenue up" when data shows decline
- **Check**: Run consistency check between retrieval and output

## Incident Tagging

When documenting failures in research notebooks or post-mortems, use these tags:

```
#failure-type: hallucination
#failure-type: ticker-confusion
#failure-type: temporal-misalignment
#failure-type: context-saturation
#failure-type: retrieval-disconnect
#failure-type: overconfident-bluffing
#failure-type: reasoning-drift
#failure-type: black-box-unclear
```

## Quick Diagnostic Questions

Before trusting an LLM-generated analysis:

1. **Source Trace**: Can I find the source document for each key claim?
2. **Ticker Validation**: Is the ticker unambiguous and correctly mapped?
3. **Time Check**: Are all data points from the expected time window?
4. **Consistency**: Does the summary match the raw data?
5. **Confidence**: Are uncertainties explicitly acknowledged?
6. **Relevance**: Does the conclusion actually answer the original question?

## Further Reading

- **WFGY ProblemMap**: A comprehensive 16-problem failure map for RAG and LLM agent pipelines
  - Reference: https://github.com/onestardao/WFGY/blob/main/ProblemMap/README.md
- **RAGFlow Documentation**: RAG failure patterns in production systems
- **LlamaIndex Guides**: Debugging retrieval and generation pipelines

## Contributing

Found a new failure mode? Add it to this checklist with:
- Symptom description
- Real-world example (anonymized if needed)
- Diagnostic check or mitigation

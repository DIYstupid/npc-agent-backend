# Agent/RAG Eval Report

Passed: `True`

## Metrics

- Total cases: 3
- Passed cases: 3
- Pass rate: 100.00%
- RAG hit rate: 100.00%
- Tool call accuracy: 100.00%
- Quest success rate: 100.00%
- Error rate: 0.00%
- Avg latency ms: 12.33
- P95 latency ms: 20
- Avg prompt tokens: 864.67
- Total prompt tokens: 2594

## Cases

### create_silver_ore_quest

- Passed: `True`
- Failures: none
- Trace ID: `b09ad9b8-029a-4e2b-bf9a-a86dfd58c1d6`
- Actual tools: `['create_quest', 'update_relationship']`
- RAG hit: `False`
- Latency ms: 20

### answer_moonwell_from_rag

- Passed: `True`
- Failures: none
- Trace ID: `f9b8d3bd-2b7b-4c4e-801a-28e99f718f3a`
- Actual tools: `[]`
- RAG hit: `True`
- Latency ms: 10

### small_talk_no_tool

- Passed: `True`
- Failures: none
- Trace ID: `85b36f21-e377-46c6-adad-b4dd6f413cb3`
- Actual tools: `[]`
- RAG hit: `False`
- Latency ms: 7

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
- Avg latency ms: 11.67
- P95 latency ms: 17
- Avg prompt tokens: 864.67
- Total prompt tokens: 2594

## Cases

### create_silver_ore_quest

- Passed: `True`
- Failures: none
- Trace ID: `353ee041-05c3-4c02-b1ab-ef239c78765d`
- Actual tools: `['create_quest', 'update_relationship']`
- RAG hit: `False`
- Latency ms: 17

### answer_moonwell_from_rag

- Passed: `True`
- Failures: none
- Trace ID: `812a50ba-d40b-4e77-a3b2-f187427cddad`
- Actual tools: `[]`
- RAG hit: `True`
- Latency ms: 9

### small_talk_no_tool

- Passed: `True`
- Failures: none
- Trace ID: `6f492a5e-bd8a-4421-8c51-cdee0ddb3744`
- Actual tools: `[]`
- RAG hit: `False`
- Latency ms: 9

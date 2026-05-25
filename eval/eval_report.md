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
- Avg latency ms: 12.67
- P95 latency ms: 18
- Avg prompt tokens: 864.67
- Total prompt tokens: 2594

## Cases

### create_silver_ore_quest

- Passed: `True`
- Failures: none
- Trace ID: `4a7c53ed-4a3c-4f45-bfd9-0fb03e5d8102`
- Actual tools: `['create_quest', 'update_relationship']`
- RAG hit: `False`
- Latency ms: 18

### answer_moonwell_from_rag

- Passed: `True`
- Failures: none
- Trace ID: `7ca75d56-d09a-4aea-a319-32c7f22f2119`
- Actual tools: `[]`
- RAG hit: `True`
- Latency ms: 10

### small_talk_no_tool

- Passed: `True`
- Failures: none
- Trace ID: `b3b3a816-0bf3-4766-9d95-348c77ebb40d`
- Actual tools: `[]`
- RAG hit: `False`
- Latency ms: 10

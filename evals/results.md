| backend | design | n | task success | tool-choice acc (exact) | tools covered | avg latency (s) | avg tokens | total cost (USD) |
|---|---|---|---|---|---|---|---|---|
| bedrock | plan | 30 | 90% | 43% | 100% | 15.9 | 22851 | 0.939 |
| bedrock | react | 30 | 87% | 43% | 90% | 7.5 | 12436 | 0.489 |
| ollama | plan | 30 | 80% | 30% | 100% | 76.9 | 9377 | 0.000 |
| ollama | react | 30 | 83% | 67% | 93% | 33.4 | 3910 | 0.000 |

Task success by category:

| category | bedrock/plan | bedrock/react | ollama/plan | ollama/react |
|---|---|---|---|---|
| calc | 100% (5) | 100% (5) | 80% (5) | 100% (5) |
| extract | 60% (5) | 60% (5) | 80% (5) | 80% (5) |
| mixed | 100% (5) | 80% (5) | 100% (5) | 100% (5) |
| retrieval | 92% (12) | 92% (12) | 67% (12) | 67% (12) |
| web | 100% (3) | 100% (3) | 100% (3) | 100% (3) |

# Template intent coverage matrix

Generated checks derive this matrix from the reviewed bank and candidate staging document. Only primary diagnostic concepts may select a template; supporting topics never hijack a plan.

| Template | Bank | Concept | Eligible intents | Positive tests | Negative intent | Supporting-only | Risk |
|---|---|---|---|---|---|---|---|
| All current templates | production/candidate | derived from manifest | template metadata | every declared intent | first undeclared standard intent | unavailable | candidate rows remain isolated |

Focused regressions include UCS + `definition`, DFS + `algorithm_trace`, A* + `algorithm_trace`, unsupported A* `property`, supporting-only BFS, and unknown concept failure. Candidate intent contracts are linted but candidates are not registered with the production selector.

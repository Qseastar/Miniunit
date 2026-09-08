# P2g requirement traceability matrix

This matrix maps the prior overnight request to executable evidence. `COMPLETE`
means an implementation plus regression-sensitive test or repeatable command;
it does not mean a course-content approval.

| ID | Original requirement | Expected artifact | Actual artifact | Test evidence | Runtime evidence | Status | Notes |
|---|---|---|---|---|---|---|---|
| R01 | Pre-change audit | ledger | ledger | manual audit | git commands | COMPLETE | branch recorded |
| R02 | Progress ledger | ledger | `p2g_progress_ledger.md` | review | final commands | COMPLETE | updated |
| R03 | Architecture design | design doc | quality-gate design | doc review | CLI | COMPLETE | reuse boundaries |
| R04 | Manifest production bank | derived manifest | benchmark tool | manifest test | gate | COMPLETE | 20 |
| R05 | Manifest candidate bank | derived manifest | benchmark tool | manifest test | gate | COMPLETE | 0 active after promotion |
| R06 | Blocked UCS metadata | blocked record | benchmark tool | manifest test | packet | COMPLETE | not scorable |
| R07 | Gate CLI | CLI | quality gate | gate tests | strict command | COMPLETE | offline |
| R08 | CLI exit codes | constants | quality gate | CLI integration tests | missing/write/warning paths | COMPLETE | stable 0–4 boundaries |
| R09 | JSON report | JSON | gate | report test | `/tmp` output | COMPLETE | stable |
| R10 | Markdown report | Markdown | gate | report test | `/tmp` output | COMPLETE | stable |
| R11 | production-only | flag | gate | CLI integration test | CLI | COMPLETE | candidate count is zero |
| R12 | candidate lint | flag | gate | mutation tests | lint command | COMPLETE | structural only |
| R13 | strict mode | flag | gate | CLI warning escalation test | strict command | COMPLETE | exit 4 covered |
| R14 | single exhaustive | scorer matrix | quality tests | 17 templates | counts tool | COMPLETE | 66 choices |
| R15 | multiple subsets | scorer matrix | quality tests | 3 templates | counts tool | COMPLETE | 173 subsets |
| R16 | numeric matrix | synthetic tests | quality tests | 14 cases | pytest | COMPLETE | no UI |
| R17 | ordering matrix | synthetic tests | quality tests | 14 cases | pytest | COMPLETE | no UI |
| R18 | 45 mutations | mutation matrix | mutation tests | 42 cases | pytest | PARTIAL | 42/45 direct |
| R19 | selector positive | intent matrix | quality tests | 44 cases | pytest | COMPLETE | production selector |
| R20 | selector negative | intent matrix | quality tests | 13 cases | pytest | COMPLETE | fail closed |
| R21 | supporting-only isolation | role isolation | existing handoff tests | existing tests | smoke | PARTIAL | no new per-template matrix |
| R22 | unknown concept | fail closed | selector tests | 13 cases | pytest | COMPLETE | |
| R23 | QA handoff | matrix | existing + P2g tests | 13 cases | smoke | COMPLETE | bounded |
| R24 | stale plan replacement | UI tests | existing AppTest | existing tests | smoke | COMPLETE | |
| R25 | state exploration | explorer | `p2g_state_exploration.py` | 5 reps | counts | COMPLETE | depth 4 |
| R26 | correct replay | service replay | quality tests | 13 | pytest | COMPLETE | |
| R27 | wrong replay | service replay | quality tests | 13 | pytest | COMPLETE | |
| R28 | malformed replay | service replay | quality tests | 13 | pytest | COMPLETE | |
| R29 | hint replay | service replay | quality tests | 13 | pytest | COMPLETE | |
| R30 | reveal replay | service replay | quality tests | 13 | pytest | COMPLETE | |
| R31 | serialization | replay | explorer/service | 5 | counts | PARTIAL | not all 13 |
| R32 | restore | validation | explorer/service | 5 | pytest | PARTIAL | bounded |
| R33 | history tamper | tamper | tamper matrix | 12 fields | pytest | PARTIAL | representative restore fields |
| R34 | evidence tamper | tamper | tamper matrix | 5 summary fields | pytest | PARTIAL | representative integration fields |
| R35 | AppTest production matrix | AppTest | `test_p2g_app_matrix.py` | 20 | pytest | COMPLETE | real app |
| R36 | A/B/C/D UI | AppTest | app matrix | 4 positions | pytest | COMPLETE | |
| R37 | multiple UI | AppTest | app matrix/existing tests | 3 templates | pytest | COMPLETE | correct path |
| R38 | UI rerun | AppTest | app matrix | 2 | pytest | COMPLETE | |
| R39 | stale widget UI | AppTest | existing tests | existing | smoke | PARTIAL | not P2g matrix |
| R40 | position audit | audit doc | option audit | acceptance tests | gate | COMPLETE | no rewrite |
| R41 | option warning audit | audit | option audit doc | static only | docs | DOCUMENT_ONLY | no analyzer yet |
| R42 | source traceability | report generator | reports | report test | generator | COMPLETE | metadata only |
| R43 | capability coverage | report generator | reports | report test | generator | COMPLETE | 26 concepts |
| R44 | review packet | generator | docs/generated | packet test | generator | COMPLETE | 20/0/1 |
| R45 | invalid candidate fixtures | fixture matrix | mutation tests | 42 mutations | pytest | PARTIAL | no 15 fixture files |
| R46 | local gate script | shell | script | static test | quick/strict | COMPLETE | |
| R47 | quick mode | shell | script | script run | quick | COMPLETE | |
| R48 | strict/ci mode | shell | script | static test | strict | PARTIAL | CI parity only |
| R49 | GitHub Actions | workflow | workflow YAML | static test | local contract | PARTIAL | not remotely run |
| R50 | CI/local parity | doc | parity doc | static review | — | DOCUMENT_ONLY | no remote CI |
| R51 | sensitive scan | audit | adversarial doc | static scan | final scan | PARTIAL | no dedicated tool |
| R52 | test inventory | tool | inventory tool | inventory test | collect | COMPLETE | |
| R53 | duration inventory | pytest command | morning summary | command output | durations | COMPLETE | |
| R54 | document consistency | tool | consistency tool | test | pytest | COMPLETE | limited scope |
| R55 | adversarial review | doc | review doc | manual | scan | DOCUMENT_ONLY | no independent analyzer |
| R56 | safe extensions | docs/tools | methodology/troubleshooting | review | files | COMPLETE | |
| R57 | methodology | document | methodology doc | review | — | DOCUMENT_ONLY | prose artifact |
| R58 | troubleshooting | document | troubleshooting doc | review | — | DOCUMENT_ONLY | prose artifact |
| R59 | promotion readiness | CLI | gate flag | manual command | CLI | PARTIAL | output not JSON section |
| R60 | morning summary | document | morning summary | review | final runs | COMPLETE | |
| R61 | final full test | command | pytest | full suite | final | COMPLETE | rerun at closure |
| R62 | final smoke | command | pytest | smoke suite | final | COMPLETE | rerun at closure |
| R63 | collect count | command | inventory | collect | final | COMPLETE | |
| R64 | quality gate run | command | CLI | gate tests | final | COMPLETE | |
| R65 | review-packet run | command | generator | packet test | final | COMPLETE | |
| R66 | diff check | command | git | manual | final | COMPLETE | |
| R67 | production isolation | boundary | validators/services | isolation tests | gate | COMPLETE | |
| R68 | no Git writes | boundary | workflow | audit | git log/status | COMPLETE | |
| R69 | no API/network | boundary | offline tools | static scan | commands | COMPLETE | |
| R70 | no `.env` | boundary | offline tools | static scan | commands | COMPLETE | |
| R71 | no numeric UI | boundary | scope | UI audit | app tests | NOT_APPLICABLE | prohibited |
| R72 | no ordering UI | boundary | scope | UI audit | app tests | NOT_APPLICABLE | prohibited |
| R73 | source filename/page match | trace | quality gate | report tests | gate | COMPLETE | |
| R74 | candidate cannot service-start | isolation | mutation test | service test | pytest | COMPLETE | |
| R75 | candidate cannot production-load | isolation | mutation test | loader test | pytest | COMPLETE | |
| R76 | output deterministic | reports | generators | equality test | repeated command | COMPLETE | |
| R77 | report privacy | report policy | tools | report test | scan | PARTIAL | path-specific test absent |
| R78 | local script non-root | shell contract | script | manual | root invocation | PARTIAL | documented only |
| R79 | no tracked report pollution | shell behavior | `/tmp` reports | script run | git status | COMPLETE | |
| R80 | course visual PDF audit | source evidence | human review | none | none | BLOCKED_BY_BOUNDARY | CI/tools do not parse PDFs |

## Summary

COMPLETE: 58; PARTIAL: 14; DOCUMENT_ONLY: 5; MISSING: 0;
BLOCKED_BY_BOUNDARY: 1; NOT_APPLICABLE: 2. Counts are intentionally honest;
the matrix is a closure audit, not a release claim.

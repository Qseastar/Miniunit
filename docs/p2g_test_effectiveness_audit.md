# P2g test-effectiveness audit

| Module / test family | Parameters | Executed path | Regression-sensitive assertion | Verdict |
|---|---:|---|---|---|
| `test_p2g_quality_gate` single choice enumeration | 17 templates | production scorer | every legal option has exact 0/1 outcome | STRONG |
| multiple-choice subset enumeration | 3 templates / 173 subsets | production scorer | only expected set passes | STRONG |
| numeric / ordering synthetic matrices | 28 cases | registered scorer functions | finite/type/order contract | ADEQUATE |
| selector intent matrix | 13 templates / 44 positive intents | `TemplateSelectionService.select` | selected ID and deterministic order | STRONG |
| handoff matrix | 13 templates | `DiagnosticHandoffService.plan` | current primary topic determines plan | ADEQUATE |
| replay/hint/reveal | 13 templates | `VerificationDiagnosticService` | history/summary/provenance changes | STRONG |
| original tamper case | 1 | session restore validation | altered score rejected | ADEQUATE |
| `test_p2g_mutation_matrix` | 42 mutations | validator/lint/service/selector | altered data fails a real boundary | STRONG |
| `test_p2g_state_machine` | 5 representatives | bounded production session exploration | state invariants and rejection count | ADEQUATE |
| `test_p2g_app_matrix` | 13 templates | real `app.py` AppTest | text render → stable ID → completed summary | STRONG |
| AppTest rerun/wrong-first | 4 paths | real `app.py` | stable ordering, first wrong does not pass | STRONG |
| `test_p2g_tamper_matrix` | 17 mutations | session restore / state integration | mutation rejected before learner-state mutation | STRONG |
| `test_p2g_cli_integration` | 3 tests | real CLI main path | production-only, lint, input/write errors, exit 4 | ADEQUATE |
| report/review packet checks | 4 functions | real generators | inventory and deterministic output | ADEQUATE |
| document / workflow static checks | 3 functions | tooling/config files | offline/trigger contract | WEAK |

No P2g test uses `assert True`; no gate test mocks production scoring. The static
workflow/document checks are deliberately classified WEAK: they detect accidental
text/config drift, not a runtime GitHub execution. The earlier “full matrix” label
for mutation/state/tamper is therefore not retained as COMPLETE.

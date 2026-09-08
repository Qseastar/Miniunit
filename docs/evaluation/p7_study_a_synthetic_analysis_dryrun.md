# P7 Study A Synthetic Analysis Dry-Run

> **THIS IS A SYNTHETIC ANALYSIS DRY-RUN.** It uses only fixed, fabricated,
> deterministic fixtures. It does not collect, read, infer or simulate any real
> participant identity or behaviour. It is not a human-study protocol, real
> participant data schema, consent material, recruitment plan, ethics decision,
> analysis-plan freeze or authorization to run Study A.

## Purpose and current boundary

This dry run answers one engineering question only:

> If lawful, approved future Study A data were available, can the repository
> calculate transparent offline candidate alignment summaries between frozen
> mastery estimates and an independent course-grounded performance criterion,
> including missing, ties and degenerate inputs?

The intended research question remains limited to **rank / monotonic alignment**
between a frozen mastery estimate and an independent course-grounded performance
criterion. It is not a claim about true mastery, ground-truth knowledge,
calibration, estimator accuracy, causal learning gains, grades, recommendation
effectiveness, treatment effects or a policy winner. Study B remains separate.

The current formal state remains unchanged:

```text
P7_READINESS_LEVEL = LEVEL_2
HUMAN_STUDY_AUTHORIZED = NO
CHECK_BEFORE_REAL_HUMAN_STUDY_RESOLVED = NO
READY_FOR_PARTICIPANT_RECRUITMENT = NO
READY_FOR_REAL_DATA_COLLECTION = NO
READY_FOR_STUDY_A_EXECUTION = NO
```

## Architecture

The new boundary is deliberately outside production:

```text
synthetic fixture JSON
  -> strict fixture validator
  -> frozen-signal P0/P2/P3 calculations
  -> synthetic item results -> concept criterion
  -> candidate rank / monotonic summaries
  -> /tmp machine-readable dry-run report
```

The runner is [run_p7_study_a_synthetic_analysis.py](../../tools/run_p7_study_a_synthetic_analysis.py).
It reuses only the P6b policy mathematics, never `DiagnosticStateIntegrationService`,
the learner-state repository, evidence gate mutation, recommender, Streamlit or any
network/API. Its default report path is:

```text
/tmp/introai_p7_study_a_synthetic_analysis.json
```

The tool writes its report atomically. It contains no question text, choice text,
raw answer, learner UUID, name, student ID, email, IP, user-agent, grade,
wall-clock timestamp, course PDF content or secret.

## Synthetic input contract

The source fixture is [p7_study_a_synthetic_fixtures.json](../../data/evaluation/p7_study_a_synthetic_fixtures.json).
It has the following non-human contract:

| Contract element | Required boundary |
| --- | --- |
| `synthetic_only` | always `true` |
| `not_approved_for_real_human_data` | always `true` |
| `candidate_analysis_not_yet_frozen_for_real_study` | always `true` |
| profile identifier | fabricated `synthetic_001`-style ID only |
| frozen evidence | deterministic, already-eligible binary signal sequence, or an explicit unavailable reason |
| external result | only item ID, binary `correct / total`, or `null + missing_reason` |
| missing vocabulary | `SYNTHETIC_TEST_VOCABULARY_ONLY` |
| forbidden fields | identity, contact, learner UUID, QA/PDF text, grades, timestamps and secrets |

The fixture is **not** a participant-data schema. The actual Study A data
minimum, linkage mechanism, retention/deletion rules, access control and final
missing-reason vocabulary remain unapproved.

## Fixture coverage

The fixture has 18 fabricated profile × concept records. It deliberately covers:

- high/high, low/low, high/low and low/high estimate–external combinations;
- repeated mastery/external values (ties);
- a positive monotonic group, no-clear-pattern group and inverse-pattern group;
- one-concept and multiple-concept external missing cases despite frozen production evidence;
- external observation with no frozen eligible evidence, so every policy is explicitly unavailable;
- a concept with a single valid pair, a constant-external-score group and policy/concept results
  below the candidate minimum pair count;
- Local Search with exactly one available external item;
- Minimax with one primary immediate item and the two-level item recorded only as exploratory.

The patterns are intentionally seeded to test plumbing. A positive synthetic
correlation is not evidence that a policy is valid, and an inverse one is not
evidence that a policy is invalid.

## P0 / P2 / P3 computation

Every available record begins with the same frozen synthetic evidence sequence:

- `P0` — P6 production-reference fixed step, `M_new = 0.65 M_old + 0.35 signal`;
- `P2` — P6b `Beta(1,1)` prior-regularized Bernoulli comparison baseline;
- `P3` — P6b count-decayed step, `alpha_n=max(0.10, 0.35/sqrt(n))`.

`P1` remains a P6b mathematical reference and is intentionally not a primary
dry-run result. No policy value is written to learner state, evidence, SQLite or
recommendation, and no policy is selected as a winner.

For example, fixture `synthetic_001` has frozen signals `[1, 1]`; the deterministic
final estimates are P0 `0.5775`, P2 `0.75`, and P3 approximately `0.510867`.
The same fixture always produces the same report.

## External item to concept criterion

The current Level 2 bank has 11 active research-only items across six concepts.
The dry run uses an explicitly labelled **synthetic test composition**, not a
future Study A assignment:

| Concept | Synthetic primary immediate items | Count |
| --- | --- | ---: |
| BFS | `p7_ext_bfs_depth_claim_a`, `p7_ext_bfs_queue_trace_b` | 2 |
| UCS | `p7_ext_ucs_cost_accumulation_a`, `p7_ext_ucs_positive_cost_bound_d` | 2 |
| A* | `p7_ext_astar_zero_heuristic_c`, `p7_ext_astar_component_change_b` | 2 |
| Local Search | `p7_ext_local_search_neighbor_a` | 1 |
| Minimax | `p7_ext_minimax_min_node_a` | 1 |
| MCTS | `p7_ext_mcts_backpropagation_a`, `p7_ext_mcts_expand_untried_child_b` | 2 |

For a complete synthetic primary result, the criterion is the transparent
`correct / total` over the listed primary items. Local Search remains `correct / 1`;
no synthetic item is added merely to make the table symmetric.

`p7_ext_minimax_two_level_b` is represented only as
`exploratory_transfer` and is excluded from every primary immediate total. It is
not a strict parallel form and cannot silently contaminate primary alignment.

The real Study A item assignment, number of items per concept, item-order and
handling of partial item administration remain `PENDING_OWNER_FREEZE`.

## Missing, ties and degenerate cases

The runner enforces:

```text
missing external result = null + synthetic missing_reason
missing external result != 0
```

If any primary item for one synthetic concept result is missing, its concept
criterion is `external_missing_no_primary_alignment_pair`; it is not included in
that policy's valid-pair count. The report preserves each reason and reports
original missing counts separately. It never drops rows while pretending the
original `N` is unchanged.

Candidate correlation is available only at three or more valid pairs and only
when both values vary. Otherwise the output is explicit:

| Boundary | Output |
| --- | --- |
| fewer than 3 valid pairs | `insufficient_data / fewer_than_three_valid_pairs` |
| all estimate values equal | `degenerate / constant_mastery_estimates` |
| all external values equal | `degenerate / constant_external_scores` |
| missing external criterion | no valid primary alignment pair |
| no frozen eligible evidence | policy `unavailable`, never a zero estimate |

Ties use average ranks for candidate Spearman rho and a tie-aware Kendall tau-b
calculation. The report also exposes concordant, discordant, estimate-tie,
external-tie and joint-tie pair counts.

## Candidate analysis outputs

For each of P0/P2/P3, the machine-readable report includes:

- overall, by-concept and by-synthetic-group valid-pair count;
- candidate Spearman rho and Kendall tau-b only when available;
- descriptive paired ordering and tie counts;
- external missing-record count and policy-unavailable record count;
- exact unavailable reason for small-N, constant values or absent frozen evidence.

The fixed synthetic groups confirm edge handling: `positive_monotonic_pattern`
has high positive candidate association by construction; `inverse_pattern` has a
negative association by construction; `constant_external_boundary` returns a
degenerate unavailable result rather than a fabricated correlation. The mixed
full fixture is deliberately not used to name a winner.

Run it locally with:

```bash
PYTHONPATH=src python tools/run_p7_study_a_synthetic_analysis.py \
  --output /tmp/introai_p7_study_a_synthetic_analysis.json
```

## Adversarial boundary audit

| Risk | Dry-run control | Result |
| --- | --- | --- |
| Synthetic-to-real leakage | Mandatory synthetic-only/not-approved flags; strict prohibited-field validation. | PASS |
| Policy-winner leakage | Report contains no p-values or winner; documentation prohibits selection. | PASS |
| Missing-as-zero | Null criterion is excluded and reason preserved. | PASS |
| Exploratory contamination | Minimax two-level item validator only permits `exploratory_transfer`. | PASS |
| Local Search symmetry pressure | One primary item is asserted and tested. | PASS |
| Small-N overinterpretation | `<3` pairs is explicitly unavailable. | PASS |
| Ties / constants | tie-aware calculation or explicit degenerate result. | PASS |
| Production side effect | No DB, learner state, evidence or recommendation imports/calls. | PASS |
| Readiness leakage | Output restates authorization `false` and checkpoint `UNRESOLVED`. | PASS |
| Privacy leakage | Fixture and report reject direct identity/contact/content/secret fields. | PASS |

## Decisions still unresolved before a real Study A

### Human owner must decide

- the approved minimal real-study data categories and pseudonymous linkage design;
- retention, deletion, backup and data-access policy;
- voluntary participation, no-consequence and withdrawal wording;
- recruitment population, incentive decision, procedure sequence and responsible contact;
- actual external item subset/composition, partial-item handling, full missing vocabulary,
  final analysis script and primary/exploratory outcome freeze;
- whether delayed outcomes are omitted or deferred until separately reviewed strict forms exist.

### Advisor must confirm

- whether the proposed limited Study A purpose and procedure are appropriate for the project;
- safeguards for classmates, collaborators or students in a dependent relationship;
- whether advisor review/approval is required before any invitation or data collection.

### College / university / institutional process must confirm

- whether Nanjing University, 健雄书院, the school/college or another body requires ethics
  review, exemption determination, registration,备案 or other approval;
- any institution-specific participant information, data governance and publication requirements.

No answer is inferred from this repository or from general university practice.

## Conclusion

> **THIS IS A SYNTHETIC ANALYSIS DRY-RUN.** It demonstrates reproducible analysis
> plumbing and safe edge-case handling only. It does not validate mastery, choose
> a policy, establish human learning or recommendation effectiveness, or make the
> project ready to recruit, collect real data or execute Study A.

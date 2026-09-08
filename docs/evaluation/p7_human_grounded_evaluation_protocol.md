# P7 Human-Grounded Evaluation Protocol

## Motivation

P6 established implementation validity for the learner-state pipeline: formal
reviewed evidence, assistance provenance, repeat handling, profile isolation,
and deterministic recommendation behave as designed. P6b compared the behavior
of several aggregation policies on the same synthetic evidence histories. Neither
phase established that a mastery estimate corresponds to independent human
learning performance. P7 prepares that external-validation study without
recruiting participants or changing production behavior.

This document distinguishes three claims:

- **Implementation validity:** P6's question is whether the system implements
  its stated evidence semantics correctly.
- **Behavioral/internal comparison:** P6b's question is how frozen evidence
  behaves under several policy formulas.
- **Human-grounded/external validity:** Study A's future question is whether
  policy estimates show useful alignment with independent, course-grounded
  assessment performance.

Only the first two have evidence today. P7 provides protocol and synthetic
instrumentation for the third; it does not claim human validation.

## Validation gap

The current production estimate is based on completed, unassisted reviewed
verification items. Reusing the same 28 production diagnostics as the outcome
would be circular: a learner could reproduce a known item or answer and appear
to validate the score that the item itself created. An external criterion must
therefore be course-grounded but independent of the production evidence event.

The P7 candidate bank is research-only. It cannot create mastery, exposure,
recommendations, or normal student UI content. It remains
`pending_owner_review` until a human owner approves each item.

## Research questions

1. How can an independent course-grounded criterion compare P0, P2, and P3?
2. Which estimate best aligns with immediate and delayed independent performance
   under one frozen evidence history?
3. Which observed differences reflect short-term responsiveness versus stability?
4. What minimum, privacy-minimized data are needed for an eventual study?
5. How should estimator validation remain separate from recommendation efficacy?

## Circular-validation risk and invariant

For every external item, P7 prohibits the same production template ID, identical
stem, identical option set, cosmetic renaming/number changes, and the same
closed instance with unchanged solution steps. An item may target the same
concept/capability family only after an explicit parallel-form audit:

- `INDEPENDENT_CAPABILITY_SAMPLE`: comparable capability, independent instance;
- `COMPLEMENTARY_CAPABILITY`: relevant adjacent capability, not a duplicate;
- `TOO_SIMILAR` or `CIRCULAR`: unusable until redesigned.

The validator rejects production-ID collisions, duplicated production stems,
unknown concepts, invalid closed answers, unknown or out-of-range source refs,
and any status other than `pending_owner_review`. Candidate files reside under
`data/evaluation/`, outside `data/diagnostic_templates.json`, and production
code does not import their validator or runner.

## Production Evidence Capability Map

The capability map is derived from the current reviewed production bank and
knowledge registry rather than hand-maintained counts. It records production
template count, capability boundaries, source expectations, current formal
evidence type, circularity risk, and external-assessment feasibility for all 26
concepts.

At the P7 baseline, 21/26 concepts have direct primary production coverage.
Concepts with no direct primary evidence are marked `DO_NOT_USE` /
`EXTERNAL_CRITERION_BLOCKED`; P7 does not invent an external criterion merely to
complete coverage. Five current blocked concepts are:

- `adversarial_search`
- `game_state_evaluation`
- `monte_carlo_search`
- `exploration_exploitation`
- `llm_search_and_test_time_scaling`

Multiple reviewed production opportunities are `HIGH_FEASIBILITY`; a single
opportunity is `MEDIUM_FEASIBILITY` and needs stronger owner scrutiny. This map
is an instrument-selection aid, not a psychometric result.

## Study A overview

Study A is an observational, offline counterfactual policy comparison. A future
participant uses one study-isolated learner profile and receives normal reviewed
production verification interactions for a selected concept subset. The live
system need not expose P2 or P3. After the formal evidence window closes, the
research workflow freezes the eligible evidence sequence and calculates each
policy offline. It then administers independent external assessment. Policies
do not change the participant's questions or recommendations during Study A.

Recommended future flow:

1. Create a clean study-specific isolated profile or temporary database.
2. Complete selected production reviewed verification interactions.
3. Apply the existing formal-evidence gate and exclude practice-only/reveal or
   otherwise assisted non-independent events according to current policy.
4. Freeze the selected session's eligible sequence before external assessment.
5. Compute P0, P2, P3 offline; retain P1 as a mathematical reference only.
6. Administer an independently reviewed immediate external item.
7. Optionally administer a different delayed parallel item and/or transfer item.
8. Export privacy-minimized local research data for analysis.

The key analysis unit is **participant x concept** because the estimate is
concept-specific. Multiple concepts from one participant are correlated and are
not independent samples; a future confirmatory analysis must use clustered,
participant-level, or mixed-effects-aware inference rather than naive independent
tests.

## Selected concept subset

Study A selects six concepts, deliberately small enough for feasibility work:

| Concept | Family / rationale |
| --- | --- |
| `breadth_first_search` | Uninformed search, two production opportunities, prerequisite-linked FIFO and optimality boundaries. |
| `uniform_cost_search` | Uninformed cost-sensitive search, sparse one-template capability. |
| `a_star_search` | Informed search, two reviewed opportunities and decomposed `f(n)=g(n)+h(n)` reasoning. |
| `local_search` | Local-search family, representation/neighborhood capability. |
| `minimax_search` | Adversarial family, alternating choice/value reasoning. |
| `monte_carlo_tree_search` | P5b-expanded Monte Carlo tree-search capability. |

The set covers uninformed, informed, local, adversarial, and MCTS families; it
contains multi-template and sparse-template concepts, prerequisite-linked
concepts, and newer reviewed coverage. It is not a claim that these six represent
all 26 concepts.

## External assessment design

External assessments use deterministic closed `single_choice` scoring only. No
LLM grader, free-form semantic grader, or production scorer/evidence service is
used. Correctness is `correct / administered` within a concept when more than one
item is used; no arbitrary difficulty weighting is introduced.

### Immediate parallel assessment — primary criterion

The primary future criterion is rank/monotonic alignment between a frozen policy
estimate and an independently owner-reviewed, immediate course-grounded concept
assessment. It tests whether policies order relative concept performance in a
useful way. It is not probability calibration and does not establish “true
mastery.” One item per selected concept should be sampled for the feasibility
pilot; the alternate item is a backup or a future parallel form, not an automatic
extra burden.

### Delayed retention — secondary criterion

Delayed performance is a secondary outcome, using a different owner-reviewed
parallel item. Practical candidate windows are same day, several days, or about
one week; the choice must be set by the eventual study constraints rather than
declared inherently scientific here. Delayed performance is valuable because P0,
P2, and P3 make different recency/stability trade-offs. Missing follow-up is
recorded as null with a reason, never as incorrect.

### Transfer / novel instance — exploratory criterion

Transfer is exploratory: a new course-allowed instance or representation that
requires applying the same concept. It should not be promoted to the primary
criterion until owner review establishes comparable scope and difficulty. It must
not be an immediate item replay.

### Teacher/expert judgment

An optional future auxiliary criterion could ask one or preferably two instructors
to rate only independently assessed responses as weak/developing/strong while
blinded to model estimates. It adds content perspective but introduces workload,
subjectivity, and an inter-rater agreement requirement. P7 collects no expert
ratings and makes no claim about their reliability.

## Candidate item bank and parallel-form audit

`data/evaluation/p7_external_assessment_candidates.json` has 12 source-grounded
candidate items: two per selected concept. Every item records its capability
slice, closed answer, source pages, production overlap classification, second
reasonable-answer audit, difficulty rationale, measures/does-not-measure
boundary, independence rationale, and `pending_owner_review` status. The bank
contains 12 `INDEPENDENT_CAPABILITY_SAMPLE` or `COMPLEMENTARY_CAPABILITY` items,
and zero `TOO_SIMILAR`/`CIRCULAR` items. That is a design-time validator result,
not owner approval.

Source evidence uses the authorized extracted course PDFs through existing chunk
IDs and physical page ranges. Candidate stems summarize rather than copy slides.
The owner review sheet must decide whether each item is sufficiently independent,
unambiguous, and comparable before any human administration.

## Human owner-review gate

The separate [owner review sheet](p7_external_assessment_owner_review_sheet.md)
lists all candidates and leaves the final decision empty. The only permitted
owner outcomes are `APPROVE_FOR_HUMAN_PILOT`, `REVISE`, and `REJECT`. P7 tooling
does not mark an item human-verified or move it into production.

## Evidence-freeze and compared-policy protocol

The evidence window is the completed formal, eligible evidence for the selected
concepts within the study session. It is frozen before external assessment, not
selected after seeing an external result. The frozen sequence is immutable and
contains no assistance/repeat event that the existing gate excludes. P7 does not
maintain a shadow learner state; it observes the frozen sequence and calculates
research estimates offline.

Parameters are fixed before human data:

- P0 `CURRENT_FIXED_STEP`: `alpha=0.35`.
- P2 `PRIOR_REGULARIZED_BERNOULLI`: `Beta(1,1)` baseline.
- P3 `COUNT_DECAYED_STEP`: `alpha_n=max(0.10, 0.35/sqrt(n))`.
- P1 `EQUAL_WEIGHT_EMPIRICAL_MEAN`: transparent mathematical reference only,
  not a core future deployment candidate because sparse evidence is extreme.

No result may tune threshold `0.6`, P2 priors, or P3 floor on the same evaluated
dataset. Any future tuning needs a separate pilot/training sample and a held-out
validation sample.

## Research event schema and privacy/data minimization

The research-only JSON export has `schema_version`, `synthetic`, `study_id`, a
random participant code, event sequence, frozen evidence sequence ID/concept and
eligible signals, P0/P2/P3 estimates, optional P1 reference, external assessment
item ID/phase/score, and explicit missing reason. Future real-study records may
also carry assistance provenance, formal/practice label, selected signal, and
production mastery before/after only when required by a documented research
question.

The code format is random `R7-XXXXXX`, never derived from a learner UUID, name,
student ID, email, or account. Participants can voluntarily retain it to match a
delayed session. Exports use event sequence/relative timing, not a needless
wall-clock timestamp. They exclude question text, free-form QA, raw answers,
course PDF content, learner UUIDs, IP/user-agent, contact information,
authorization data, access code, and API key. Default export is local JSON under
`/tmp`, with no server upload. Exact time + class/sequence combinations are also
avoided because they can increase re-identification risk.

## Missing-data semantics

An external result is `null` with a controlled `missing_reason` when a
participant stops before assessment, a delayed session is missing, or an item is
not administered. Null is not zero and is excluded from correctness summaries
unless a later protocol explicitly defines a missing-data analysis. This preserves
the distinction between nonresponse and incorrect response.

## Synthetic dry-run

`tools/run_p7_synthetic_study.py` is synthetic-only by default. It reuses P6b's
integration-faithful temporary evidence traces, freezes formal sequences, runs
P0/P2/P3 offline, attaches deterministic synthetic external results, and exports
`/tmp/introai_p7_synthetic_study_export.json`. It does not write a production
learner state, exposure, recommendation, production database, or candidate item
to the student UI. Its output explicitly has `synthetic: true`.

The eight deterministic scenarios are:

| ID | Scenario | Purpose |
| --- | --- | --- |
| S1 | strong evidence + strong external | aligned positive control |
| S2 | weak evidence + weak external | aligned negative control |
| S3 | contradictory evidence + strong external | distinguish recency/stability |
| S4 | contradictory evidence + weak external | distinguish recency/stability |
| S5 | policy threshold disagreement | preserve policy contrast |
| S6 | assisted/repeat present but excluded | verify evidence gate reuse |
| S7 | stopped before external | null/missing handling |
| S8 | delayed session missing | null delayed handling |

Synthetic rows are pipeline fixtures only. They are never human findings and are
not used for p-values, effect sizes, power claims, or policy selection.

## Analysis plan and hypotheses

First describe, per policy, frozen mastery distributions, external score
distributions, missingness, and threshold classifications. The primary analysis
is a rank/monotonic association (Spearman or Kendall as appropriate) between
policy estimate and immediate independent concept score at the participant x
concept level. Small samples and ties may make intervals/descriptive reporting
more appropriate than inferential claims.

Policy comparisons are paired: P0/P2/P3 estimates from the same frozen evidence
history are compared against the same external score. Immediate versus delayed
associations are compared descriptively. Threshold `mastery >= 0.6` versus a
predefined external performance band is exploratory; the band must be decided
before outcomes are inspected. There is no undefined “calibration” claim because
the current mastery score has no established probability semantics.

Pre-specified, falsifiable hypotheses:

- H1: P0's association may be stronger for immediate than delayed external
  performance if its recency sensitivity captures short-term state.
- H2: P2 may produce less extreme estimates than P0 under sparse evidence;
  this can be assessed by the distribution and its external alignment.
- H3: P3 may trade some immediate responsiveness for greater stability across
  contradictory histories; alignment under S3/S4-like human histories tests it.
- H4: P0/P2/P3 threshold disagreements may classify low external performance
  differently. No policy is presumed superior.

## Participant burden and validity threats

Study A is a feasibility pilot, not an exam. A recommended first pass is a
balanced/incomplete block: selected production interactions plus one immediate
external item per concept actually sampled, instead of administering all 12
candidates to every participant. The final number and duration must be piloted;
P7 intentionally does not assert that any fixed N or minute count is sufficient.
If a protocol reaches 40–60 questions or more than roughly an hour, it should be
reduced before use.

Threats include circularity and hidden item overlap; practice effects and
immediate recall; small or self-selected samples; concept-difficulty differences;
external-item quality; participant-within repeated-measure dependence; missing
delayed follow-up; heterogeneous assistance and prior course knowledge; sparse
evidence; frozen but potentially suboptimal parameter choices; and the fact that
independent assessment is an imperfect external criterion rather than true
mastery. Owner review, parallel forms, explicit assistance/exposure boundaries,
and a study-isolated profile mitigate but do not eliminate these threats.

## Ethics/approval checkpoint

Before a real human study, the owner must verify voluntary participation,
research purpose, no grade consequence, right to stop, data collected,
retention/deletion policy, and relevant teacher/institutional approval
requirements. This is `CHECK_BEFORE_REAL_HUMAN_STUDY`, not a claim that a
particular ethics process is or is not required. P7 has recruited no one and
collected no human data.

## Human-study readiness levels

- **Level 0:** protocol draft only.
- **Level 1:** synthetic pipeline validated.
- **Level 2:** external candidates owner-reviewed.
- **Level 3:** small feasibility pilot ready.
- **Level 4:** human pilot completed.
- **Level 5:** independent validation study.

P7 reaches **Level 1 only**. Owner review could prepare Level 2 later; it is not
complete merely because a machine validator passes.

## Future Study B: recommendation intervention

Recommendation usefulness is a downstream intervention question, separate from
estimator alignment. A future Study B could compare a mastery-driven recommended
sequence with a pre-specified non-personalized sequence using appropriate
randomization or controlled counterbalancing, then measure later learning
outcomes. It must not be inferred from Study A.

## Valid future claims and unsupported claims

If an owner-reviewed, future human Study A is completed as specified, it could
support limited claims such as: “under this course-grounded protocol, a policy
showed stronger alignment with an independent immediate or delayed assessment.”
It cannot by itself establish true knowledge, universal superiority, probability
calibration, causal learning improvement, recommendation usefulness, or
generalization outside the studied concepts/participants.

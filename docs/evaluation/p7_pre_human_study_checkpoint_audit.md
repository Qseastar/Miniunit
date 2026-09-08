# P7 CHECK_BEFORE_REAL_HUMAN_STUDY checkpoint audit

> 审计日期：2026-08-12。本文是仓库内的研究流程与参与者保护缺口审计，供 human owner、指导教师和相关机构核实使用。它不是知情同意书、招募材料、伦理审批申请或真人研究授权。

## Decision boundary

当前仓库确认的项目状态为：

```text
P7_READINESS_LEVEL = LEVEL_2
HUMAN_STUDY_AUTHORIZED = NO
CHECK_BEFORE_REAL_HUMAN_STUDY = UNRESOLVED
CHECKPOINT_READY_FOR_OWNER_REVIEW = YES
```

Level 2 只表示 11 个 research-only external assessment items 已完成 human-owner
内容审核。它不表示真人研究获批，也不表示 external result 是 true mastery、ground
truth、calibrated probability、learning gains 或 recommendation effectiveness 证据。
本次审计没有修改 Level 2 decision、external item、production diagnostics、learner
state、mastery、recommendation、evidence gate 或数据库 schema。

## Evidence and scope

本审计只使用仓库内的以下材料：

- `docs/evaluation/p7_human_grounded_evaluation_protocol.md`
- `docs/evaluation/p6_learner_state_measurement_audit.md`
- `docs/evaluation/p6b_aggregation_policy_comparison.md`
- `docs/evaluation/p7_readiness_promotion_audit.md`
- `docs/evaluation/p7_level2_owner_readiness_decision.md`
- `docs/learner_state_privacy.md`
- `data/evaluation/p7_readiness_status.json`
- `tools/run_p7_synthetic_study.py` 及其离线测试

仓库内没有 participant-facing information/consent material、recruitment protocol、
retention/deletion policy、complaint procedure、访问权限矩阵或南京大学/健雄书院/学院/
指导教师/伦理机构的正式要求文件。因此，外部机构要求一律保留为
`UNKNOWN_REQUIRES_EXTERNAL_VERIFICATION`，不根据常识推断“需要”或“不需要”审批。

## Checkpoint matrix

状态只能使用：`SATISFIED_BY_EXISTING_REPO`、`PARTIALLY_SPECIFIED`、
`NOT_SPECIFIED`、`UNKNOWN_REQUIRES_EXTERNAL_VERIFICATION`、`NOT_APPLICABLE`。

| ID | Category | Status | Repository evidence | Gap before real participants |
| --- | --- | --- | --- | --- |
| A | Research purpose / scope | `PARTIALLY_SPECIFIED` | Study A is defined as frozen-policy estimate vs independent course-grounded performance; Study B is separate. | Freeze the exact participant-facing purpose and selected concept/item subset. |
| B | Voluntary participation | `NOT_SPECIFIED` | Protocol says the owner must verify voluntariness; no participant-facing rule exists. | State that participation and every activity are voluntary and non-participation has no penalty. |
| C | No grade consequence | `NOT_SPECIFIED` | No repository rule covers grades, course standing, research opportunities or peer relations. | Owner must approve explicit no-grade/no-benefit-consequence wording. |
| D | Withdrawal rights | `NOT_SPECIFIED` | Protocol mentions a right to stop but does not define timing, scope or already-exported data handling. | Decide how to stop, request deletion, and handle data already included in frozen aggregates. |
| E | Participant information / disclosure | `PARTIALLY_SPECIFIED` | Protocol documents research boundary, external-criterion limits and several excluded fields. | Prepare participant-facing explanation of purpose, procedures, risks, data use, contacts and withdrawal. |
| F | Data minimization | `PARTIALLY_SPECIFIED` | Existing export excludes names, student IDs, email, IP/user-agent, UUID, QA/answers, PDFs and secrets. | The minimum real-study dataset and its approval are not frozen: `DATA_SCHEMA_FOR_HUMAN_STUDY = NOT_YET_APPROVED`. |
| G | Data retention | `NOT_SPECIFIED` | No duration or storage lifecycle is stated. | Decide duration, storage location, backups and end-of-study handling. |
| H | Data deletion | `NOT_SPECIFIED` | No participant withdrawal deletion procedure or backup deletion rule is stated. | Define who can request deletion, what is deleted, and how derived exports/backups are handled. |
| I | Confidentiality / pseudonymization | `PARTIALLY_SPECIFIED` | Random `R7-XXXXXX` codes and exclusion of direct identifiers are specified. | Approve the linkage boundary, code custody, access controls and re-identification protections. |
| J | Recruitment boundaries | `NOT_SPECIFIED` | No eligible/ineligible population, age boundary or invitation channel is defined. | Define who may be invited, who must be excluded, and how invitations avoid pressure. |
| K | Compensation / incentives | `NOT_SPECIFIED` | No compensation, gift, credit or reward decision exists. | Human owner must decide whether there is any incentive and assess undue influence. |
| L | Vulnerable or dependent participants | `NOT_SPECIFIED` | No age/minor or dependency screening rule exists. | Define exclusion/escalation rules before any invitation. |
| M | Instructor / advisor relationship | `UNKNOWN_REQUIRES_EXTERNAL_VERIFICATION` | Repository does not establish whether invitees are students, collaborators or people whose grades/opportunities can be influenced. | Confirm relationship boundaries and an independent contact/complaint route. |
| N | School / college / university requirements | `UNKNOWN_REQUIRES_EXTERNAL_VERIFICATION` | No official Nanjing University, 健雄书院 or school requirement is present in the repository. | Ask the relevant office/advisor whether registration, review or notification is required. |
| O | Ethics / institutional review requirements | `UNKNOWN_REQUIRES_EXTERNAL_VERIFICATION` | Protocol intentionally leaves the approval question open; no official determination is present. | Obtain an institution-specific answer; do not infer exemption or mandatory approval. |
| P | Study procedure freeze | `PARTIALLY_SPECIFIED` | A future flow, evidence freeze and immediate/delayed/transfer roles are described. | Freeze production version, study profile, session order, stopping rules, item assignment and export procedure. |
| Q | Instrument freeze | `PARTIALLY_SPECIFIED` | Level 2 owner-reviewed bank has 11 active items across six concepts; Local Search is intentionally asymmetric. | Freeze the administered subset and role of each item; do not call Minimax two-level a strict parallel form. |
| R | Data analysis plan freeze | `PARTIALLY_SPECIFIED` | P0/P2/P3, rank/monotonic primary analysis, missingness and hypotheses are documented. | Freeze primary/exploratory outcomes, missing-data analysis, exclusion rules and analysis script version before data. |
| S | Missing-data handling | `PARTIALLY_SPECIFIED` | External missing results use `null + missing_reason`; synthetic S7/S8 exercise this. | Approve the complete reason vocabulary and handling for withdrawal, technical failure, skipped item and incomplete production evidence. |
| T | Adverse-event / complaint handling | `NOT_SPECIFIED` | No complaint contact, incident route or response timeline exists. | Define a safe contact and escalation/recording procedure before recruitment. |
| U | Responsible researcher contact | `NOT_SPECIFIED` | No participant-facing responsible-person contact is recorded. | Owner/advisor must provide a contact identity/channel in participant material. |
| V | Data-access permissions | `NOT_SPECIFIED` | Local `/tmp` export and privacy exclusions are described, but roles and permissions are not. | Define who may access raw/derived data, where it is stored and how access is revoked. |
| W | Publication / presentation boundary | `PARTIALLY_SPECIFIED` | Protocol lists supported and unsupported scientific claims. | Decide whether anonymized aggregates may appear in reports, presentations, preprints or papers and how consent covers that use. |
| X | Participant debriefing | `NOT_SPECIFIED` | No deception or debriefing decision is recorded. | Owner must decide whether a closing explanation is needed and document it if applicable. |

### Explicit participation relationship scope

```text
PARTICIPANT_RELATIONSHIP_SCOPE = NOT_YET_DEFINED
```

The repository does not define whether future invitees are classmates, project members,
students of the instructor/advisor, collaborators, acquaintances, or people whose grades,
roles or research opportunities could be influenced by the owner. This must be resolved before
recruitment; it cannot be replaced by an automated test result.

## What is already useful, but not sufficient

The current repository gives a sound research-only technical baseline:

- external results are described only as an independent course-grounded performance criterion;
- the active bank is outside production and cannot write mastery, exposure, learner state or recommendation;
- the synthetic runner is offline-only and marks missing external results as `null` with a reason;
- random study codes are not derived from learner UUIDs or direct identifiers;
- protocol and P6/P6b records distinguish formal evidence, practice/repeat, assistance and research-only policy comparison;
- Study A and future Study B remain separate.

These facts do not establish consent, institutional approval, participant protection, retention,
deletion, access control or a completed human-study procedure.

## Missing-data semantics audit

The current rule remains:

```text
missing = null + missing_reason
```

It must never be encoded as `0`. Existing synthetic reasons include
`participant_stopped_before_external_assessment`, `delayed_session_missing` and
`concept_assessment_not_administered`. Before real data collection, the owner must decide
whether `technical_failure`, `item_skipped`, `withdrawn`, and `incomplete_production_evidence`
need separate controlled reasons. No new participant schema is implemented by this audit.

## Strict parallel-form boundary

`strict immediate/delayed parallel forms = unavailable` remains true.

- **Immediate Study A alignment:** the absence of a strict delayed pair does not by itself make an
  immediate, owner-frozen, independent criterion impossible. A single selected item per concept
  can support the stated feasibility question if the human-study checkpoint is resolved and the
  administered subset is frozen. It cannot support claims beyond that criterion.
- **Delayed retention:** the current bank cannot be represented as an already-approved strict
  immediate/delayed pair. A delayed result therefore requires a separately reviewed form or an
  explicit decision to omit delayed claims; missing follow-up remains `null + missing_reason`.
- **Transfer:** `p7_ext_minimax_two_level_b` remains `TRANSFER_EXPLORATORY_ONLY`; it is not a
  strict parallel form and must not become a primary retention or calibration measure.

## Questions requiring advisor / institutional confirmation

Each question is deliberately unanswered.

1. **ADVISOR_TO_CONFIRM** — For an early research project inviting students to complete a
   system learning test or contributing performance data, is additional advisor approval required?
2. **ADVISOR_TO_CONFIRM** — If invitees are students taught, supervised or evaluated by the
   owner/advisor, what safeguards or independent recruitment route are required?
3. **OWNER_TO_VERIFY** — Is written participant information and/or consent required for this
   anonymous, minimal, non-grade-affecting study?
4. **OWNER_TO_VERIFY** — Which exact data categories may be collected, exported, linked across
   sessions or retained for analysis?
5. **ADVISOR_TO_CONFIRM** — Does the project require registration, ethics review, exemption
   determination,备案 or other submission to 南京大学, 健雄书院, the school, college or an
   institutional review body?
6. **ADVISOR_TO_CONFIRM** — Does the answer change if participants are adults, no grades are
   involved, and only minimal anonymous performance data are collected?
7. **OWNER_TO_VERIFY** — What retention period, storage location, backup rule and deletion
   procedure apply, including after participant withdrawal?
8. **OWNER_TO_VERIFY** — Who may access raw exports and derived aggregates, and how is access
   revoked at study end?
9. **OWNER_TO_VERIFY** — Are any incentives, gifts, course credit or other benefits planned,
   and could they create perceived pressure?
10. **ADVISOR_TO_CONFIRM** — Are future presentations, thesis/project reports, preprints or
    papers allowed to use anonymous aggregate results, and what disclosure is required?
11. **OWNER_TO_VERIFY** — What is the responsible researcher contact and complaint/escalation
    route shown to participants?

No answer to these questions is inferred from common university practice.

## Risk register

| Risk | Current status | Mitigation requirement | Blocker before human study? |
| --- | --- | --- | --- |
| Coercion / perceived pressure | `PARTICIPANT_RELATIONSHIP_SCOPE = NOT_YET_DEFINED` | Define independent voluntary recruitment and relationship safeguards. | YES |
| Grade-related misunderstanding | No participant-facing no-grade rule. | Explicitly state no grade/opportunity consequence and verify with advisor. | YES |
| Privacy leakage | Technical export boundary is strong; real-study access/retention is undefined. | Approve minimum fields, access roles and storage controls; test exports before use. | YES |
| Identity linkage | Random code is defined; linkage custody and separation are not. | Decide whether linkage is needed and keep it outside learner UUID/account identifiers. | YES |
| Overclaiming mastery | Protocol and Level 2 decision explicitly prohibit it. | Preserve “independent course-grounded performance criterion” wording in all materials. | NO (controlled, must remain monitored) |
| Incomplete withdrawal procedure | No procedure for already-exported/derived data. | Owner approves withdrawal and deletion semantics before collection. | YES |
| Undefined retention | No duration, backup or end-of-study rule. | Set and document retention/deletion/access policy. | YES |
| Institutional requirement unknown | No official Nanjing University/健雄书院/teacher evidence in repo. | Obtain external determination; do not infer exemption or mandatory review. | YES |
| Instrument version drift | Level 2 bank is owner-reviewed, but administered subset/version is not frozen. | Record immutable bank/version and item assignment before data. | YES |
| Production version drift | Protocol requires freezing evidence before external assessment, but no run lock exists. | Freeze production commit, registry/template inventory and study session boundary. | YES |
| Missing-data misclassification | `null + missing_reason` is defined for synthetic pipeline. | Approve complete controlled reason list and analysis treatment. | YES |
| Small-sample overinterpretation | Protocol calls this a feasibility pilot and rejects calibration/causal claims. | Predefine descriptive/rank analysis limits and avoid inferential overclaiming. | YES for claims, not a technical blocker |
| Delayed-form circularity | Strict immediate/delayed pair unavailable. | Either obtain a reviewed pair or omit delayed-retention claims. | YES for delayed claims; NO for bounded immediate feasibility |

Automated tests validate software invariants only; they do not mitigate participant-protection,
coercion or institutional-approval risks.

## Study A boundary after this audit

The intended Study A question remains frozen at the scope level:

> Compare frozen mastery-policy estimates with an independent course-grounded performance
> criterion using rank/monotonic alignment.

It is not calibration against true mastery, recommendation effectiveness, learning gains, or a
treatment/control intervention. Study B remains separate. The audit does not choose a policy
winner, sample size, power analysis, treatment assignment or delayed window.

## Readiness decision

```text
LEVEL_2_STATUS_VALID = YES
HUMAN_STUDY_AUTHORIZED = NO
CHECK_BEFORE_REAL_HUMAN_STUDY_RESOLVED = NO
CHECKPOINT_READY_FOR_OWNER_REVIEW = YES
READY_FOR_ADVISOR_INSTITUTIONAL_VERIFICATION = YES
READY_FOR_PARTICIPANT_RECRUITMENT = NO
READY_FOR_REAL_DATA_COLLECTION = NO
READY_FOR_STUDY_A_EXECUTION = NO
READY_TO_COMMIT = YES
```

The next action is to take the question sheet to the human owner, advisor and relevant
institutional contact, then record their answers in a separately reviewed checkpoint decision.
Do not recruit, create participant IDs, collect real data or run Study A before that checkpoint
is explicitly resolved.

## Audit boundary and repository hygiene

This was a documentation-only audit. It did not create a consent form, recruitment material,
participant schema, participant list, participant ID, database migration or production code.
It did not read `.env`, call a network/API, use real participant data, or modify Git history.

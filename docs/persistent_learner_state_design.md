# Persistent Learner State v1

## Persistence boundary

`learner.py` and P5B remain the domain authority. Streamlit keeps a runtime
cache in `st.session_state`; `SQLiteLearnerStateRepository` only saves and
restores already-validated state. `app.py` does not issue SQL.

The repository stores profile metadata, per-concept mastery, misconception
identifiers, and minimal reviewed-verification event summaries. It never
stores free-form questions, student answer text, LLM output, course chunks,
prompts, or credentials.

## Identity and location

The browser URL carries `learner=<random UUID>`. It is an anonymous local
profile key, not authentication. The default database is
`~/.introai_tutor/learner_state.sqlite3`; set `INTROAI_STATE_DB` to override
the location for a local deployment or test. The database is Git-ignored.

## Schema and migration

SQLite `PRAGMA user_version` is the only schema-version mechanism. Version 2
contains `learner_profiles`, `concept_state`, `misconception_state`, and
`evidence_events`. A transactional v1-to-v2 migration adds the audit tables
without deleting prior profile or mastery rows. Newer unknown versions fail
closed.

## Save and restore

After deterministic verification completes and the existing integration
service has updated learner state, the app queues one UUID event and saves the
state plus a compact evidence payload in one transaction. `event_id` is unique:
same payload is a no-op; different payload for the same ID fails closed.

On a new Streamlit session, the profile is loaded by URL UUID, validated
against current concepts/templates, and copied into session state. In-progress
diagnostics, form controls, QA cards, plans, errors, and reset confirmations
are intentionally not restored.

from uuid import UUID

from introai_tutor.learner_profile import (
    LEARNER_QUERY_PARAM,
    normalize_learner_id,
    resolve_learner_id,
    start_new_profile,
)


def test_missing_profile_id_creates_random_uuid_in_query_mapping():
    query = {}
    learner_id, created = resolve_learner_id(query)

    assert created is True
    assert str(UUID(learner_id)) == learner_id
    assert query[LEARNER_QUERY_PARAM] == learner_id


def test_valid_profile_id_is_preserved_and_invalid_value_is_replaced():
    valid = "4ed2149c-6dd3-4a23-9c4d-94ea4edb63fd"
    assert resolve_learner_id({LEARNER_QUERY_PARAM: valid}) == (valid, False)

    query = {LEARNER_QUERY_PARAM: "../../not-a-profile"}
    learner_id, created = resolve_learner_id(query)
    assert created is True
    assert learner_id != "../../not-a-profile"
    assert normalize_learner_id("student@example.edu") is None


def test_new_profile_changes_only_anonymous_query_identifier():
    query = {LEARNER_QUERY_PARAM: "4ed2149c-6dd3-4a23-9c4d-94ea4edb63fd"}
    learner_id = start_new_profile(query)
    assert query == {LEARNER_QUERY_PARAM: learner_id}
    assert str(UUID(learner_id)) == learner_id

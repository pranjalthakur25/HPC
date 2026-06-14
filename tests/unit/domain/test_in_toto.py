"""Unit tests for ``domain.models.in_toto`` -- pure data, no doubles needed."""

from __future__ import annotations

import dataclasses
import json

import pytest

from hpc_provenance.domain.models.in_toto import IN_TOTO_STATEMENT_TYPE, InTotoStatement
from hpc_provenance.domain.models.provenance import ResourceDescriptor


def _statement(**overrides: object) -> InTotoStatement:
    defaults: dict[str, object] = {
        "subjects": (ResourceDescriptor(name="model.safetensors", digest={"sha256": "b" * 64}),),
        "predicate_type": "https://slsa.dev/provenance/v1",
        "predicate": {"buildDefinition": {}, "runDetails": {}},
    }
    defaults.update(overrides)
    return InTotoStatement(**defaults)  # type: ignore[arg-type]


def test_default_type_is_in_toto_statement_v1() -> None:
    statement = _statement()

    assert statement.type_ == IN_TOTO_STATEMENT_TYPE == "https://in-toto.io/Statement/v1"


def test_to_dict_matches_in_toto_statement_v1_shape() -> None:
    statement = _statement()

    assert statement.to_dict() == {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": "model.safetensors", "digest": {"sha256": "b" * 64}}],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {"buildDefinition": {}, "runDetails": {}},
    }


def test_to_dict_serializes_each_subject() -> None:
    statement = _statement(
        subjects=(
            ResourceDescriptor(name="a", digest={"sha256": "a" * 64}),
            ResourceDescriptor(name="b", digest={"sha256": "b" * 64}),
        )
    )

    assert statement.to_dict()["subject"] == [
        {"name": "a", "digest": {"sha256": "a" * 64}},
        {"name": "b", "digest": {"sha256": "b" * 64}},
    ]


def test_to_dict_handles_empty_subjects() -> None:
    statement = _statement(subjects=())

    assert statement.to_dict()["subject"] == []


def test_to_json_round_trips_to_dict() -> None:
    statement = _statement()

    assert json.loads(statement.to_json()) == statement.to_dict()


def test_custom_type_is_respected() -> None:
    statement = _statement(type_="https://in-toto.io/Statement/v0.1")

    assert statement.to_dict()["_type"] == "https://in-toto.io/Statement/v0.1"


def test_statement_is_immutable() -> None:
    statement = _statement()

    with pytest.raises(dataclasses.FrozenInstanceError):
        statement.predicate_type = "other"  # type: ignore[misc]


def test_from_dict_round_trips_to_dict() -> None:
    statement = _statement()

    assert InTotoStatement.from_dict(statement.to_dict()) == statement


def test_from_json_round_trips_to_json() -> None:
    statement = _statement()

    assert InTotoStatement.from_dict(json.loads(statement.to_json())) == statement


def test_from_dict_handles_empty_subjects() -> None:
    statement = _statement(subjects=())

    assert InTotoStatement.from_dict(statement.to_dict()) == statement


def test_from_dict_defaults_type_when_missing() -> None:
    data = _statement().to_dict()
    del data["_type"]

    assert InTotoStatement.from_dict(data).type_ == IN_TOTO_STATEMENT_TYPE

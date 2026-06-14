"""Unit tests for ``domain.models.provenance`` -- pure data, no doubles needed."""

from __future__ import annotations

from hpc_provenance.domain.models.provenance import ResourceDescriptor


def test_resource_descriptor_to_dict_omits_unset_fields() -> None:
    assert ResourceDescriptor().to_dict() == {}


def test_resource_descriptor_to_dict_includes_set_fields() -> None:
    descriptor = ResourceDescriptor(
        name="model.safetensors",
        uri="file:///out/model.safetensors",
        digest={"sha256": "b" * 64},
        download_location="https://example.org/artifacts/model.safetensors",
        media_type="application/octet-stream",
        annotations={"sizeBytes": 123456},
    )

    assert descriptor.to_dict() == {
        "name": "model.safetensors",
        "uri": "file:///out/model.safetensors",
        "digest": {"sha256": "b" * 64},
        "downloadLocation": "https://example.org/artifacts/model.safetensors",
        "mediaType": "application/octet-stream",
        "annotations": {"sizeBytes": 123456},
    }


def test_resource_descriptor_to_dict_omits_empty_digest_and_annotations() -> None:
    descriptor = ResourceDescriptor(name="job.log", digest={}, annotations={})

    result = descriptor.to_dict()

    assert "digest" not in result
    assert "annotations" not in result


def test_resource_descriptor_from_dict_round_trips_full_shape() -> None:
    descriptor = ResourceDescriptor(
        name="model.safetensors",
        uri="file:///out/model.safetensors",
        digest={"sha256": "b" * 64},
        download_location="https://example.org/artifacts/model.safetensors",
        media_type="application/octet-stream",
        annotations={"sizeBytes": 123456},
    )

    assert ResourceDescriptor.from_dict(descriptor.to_dict()) == descriptor


def test_resource_descriptor_from_dict_empty_mapping_yields_defaults() -> None:
    assert ResourceDescriptor.from_dict({}) == ResourceDescriptor()

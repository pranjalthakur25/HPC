"""Mapping logic for SLSA Provenance v1 predicates.

This module is the *only* place that knows how to translate between
``domain`` models and the SLSA v1 predicate JSON shape
(https://slsa.dev/spec/v1.0/provenance). It is split into two directions:

- **Context -> predicate components**: ``build_definition_from_context`` and
  ``run_details_from_context`` turn a ``ProvenanceContext`` (the "collected
  metadata models") into ``BuildDefinition``/``RunDetails`` dataclasses.
- **Predicate -> dict**: ``predicate_to_dict`` and its helpers turn a
  ``SLSAProvenancePredicate`` dataclass tree into a JSON-serializable
  ``dict`` matching the SLSA v1 schema (camelCase keys).

Keeping this logic out of ``domain.models.provenance`` keeps those
dataclasses pure data (no knowledge of JSON shape or of
``ProvenanceContext``), and keeps the mapping independently testable and
swappable (e.g. a future SLSA v1.1 mapper).

Scheduler extensibility: ``build_definition_from_context`` dispatches on
``context.job_metadata.job_id.scheduler`` via the ``_BUILD_TYPES`` and
``_INTERNAL_PARAMETERS_MAPPERS`` registries below. Adding a new HPC
scheduler is an *additive* change: add a new ``SchedulerType`` member, a new
job-metadata model (if needed), a mapper function, and an entry in both
registries -- no existing mapping code needs to change.
"""

from __future__ import annotations

from collections.abc import Callable

from hpc_provenance.domain.enums import SchedulerType
from hpc_provenance.domain.exceptions import ProvenanceGenerationError
from hpc_provenance.domain.models.artifact import Artifact
from hpc_provenance.domain.models.git_metadata import GitRepositoryMetadata
from hpc_provenance.domain.models.provenance import (
    BuildDefinition,
    BuilderIdentity,
    ResourceDescriptor,
    RunDetails,
    SLSAProvenancePredicate,
)
from hpc_provenance.domain.models.provenance_context import ProvenanceContext
from hpc_provenance.domain.models.provenance_metadata import BuildMetadata
from hpc_provenance.domain.models.scheduler_metadata import ResourceUsage, SlurmJobMetadata

# ---------------------------------------------------------------------------
# Context -> predicate components
# ---------------------------------------------------------------------------


def _resource_usage_to_dict(usage: ResourceUsage | None) -> dict[str, object] | None:
    """Map a ``ResourceUsage`` to its ``internalParameters.resourceUsage`` JSON shape.

    Fields that are ``None`` are omitted; returns ``None`` if no fields are set.
    """
    if usage is None:
        return None

    result: dict[str, object] = {}
    if usage.elapsed_seconds is not None:
        result["elapsedSeconds"] = usage.elapsed_seconds
    if usage.cpu_time_seconds is not None:
        result["cpuTimeSeconds"] = usage.cpu_time_seconds
    if usage.max_rss_bytes is not None:
        result["maxRssBytes"] = usage.max_rss_bytes
    if usage.max_vm_size_bytes is not None:
        result["maxVmSizeBytes"] = usage.max_vm_size_bytes
    return result or None


def _slurm_internal_parameters(job_metadata: SlurmJobMetadata) -> dict[str, object]:
    allocation = job_metadata.allocation
    parameters: dict[str, object] = {
        "scheduler": SchedulerType.SLURM.value,
        "jobId": str(job_metadata.job_id),
        "jobName": job_metadata.job_name,
        "user": job_metadata.user_name,
        "account": job_metadata.account,
        "state": job_metadata.state.value,
        "exitCode": job_metadata.exit_code,
        "partition": allocation.partition,
        "numNodes": allocation.num_nodes,
        "numTasks": allocation.num_tasks,
        "cpusPerTask": allocation.cpus_per_task,
        "gpusPerNode": allocation.gpus_per_node,
        "nodeList": list(allocation.node_list),
    }
    resource_usage = _resource_usage_to_dict(job_metadata.resource_usage)
    if resource_usage is not None:
        parameters["resourceUsage"] = resource_usage
    return parameters


_BUILD_TYPES: dict[SchedulerType, str] = {
    SchedulerType.SLURM: "https://hpc-provenance.dev/build-types/slurm-job/v1",
}

_INTERNAL_PARAMETERS_MAPPERS: dict[SchedulerType, Callable[[SlurmJobMetadata], dict[str, object]]] = {
    SchedulerType.SLURM: _slurm_internal_parameters,
}


def _external_parameters(job_metadata: SlurmJobMetadata) -> dict[str, object]:
    return {
        "jobScript": " ".join(job_metadata.submit_command),
        "workingDirectory": str(job_metadata.working_directory),
    }


def resource_descriptor_from_artifact(artifact: Artifact) -> ResourceDescriptor:
    """Map a collected ``Artifact`` to an in-toto ``ResourceDescriptor``."""
    annotations: dict[str, object] = {}
    if artifact.size_bytes is not None:
        annotations["sizeBytes"] = artifact.size_bytes

    return ResourceDescriptor(
        name=artifact.name,
        uri=artifact.uri,
        digest=artifact.digest.as_digest_set(),
        media_type=artifact.media_type,
        annotations=annotations or None,
    )


def resource_descriptor_from_git_metadata(git_metadata: GitRepositoryMetadata) -> ResourceDescriptor:
    """Map collected ``GitRepositoryMetadata`` to a source ``ResourceDescriptor``."""
    annotations: dict[str, object] = {"isDirty": git_metadata.is_dirty}
    if git_metadata.branch is not None:
        annotations["branch"] = git_metadata.branch
    if git_metadata.tags:
        annotations["tags"] = list(git_metadata.tags)

    return ResourceDescriptor(
        uri=git_metadata.remote_url,
        digest={"gitCommit": git_metadata.commit.sha},
        annotations=annotations,
    )


def _resolved_dependencies(context: ProvenanceContext) -> tuple[ResourceDescriptor, ...]:
    dependencies = [resource_descriptor_from_artifact(artifact) for artifact in context.materials]
    if context.git_metadata is not None:
        dependencies.append(resource_descriptor_from_git_metadata(context.git_metadata))
    return tuple(dependencies)


def build_definition_from_context(context: ProvenanceContext) -> BuildDefinition:
    """Map a ``ProvenanceContext`` to a SLSA ``BuildDefinition``.

    Raises:
        ProvenanceGenerationError: if ``context.job_metadata.job_id.scheduler``
            has no registered build type / internal-parameters mapper.
    """
    job_metadata = context.job_metadata
    scheduler = job_metadata.job_id.scheduler

    try:
        build_type = _BUILD_TYPES[scheduler]
        internal_parameters_mapper = _INTERNAL_PARAMETERS_MAPPERS[scheduler]
    except KeyError as exc:
        raise ProvenanceGenerationError(
            f"No SLSA build-definition mapping registered for scheduler {scheduler!r}"
        ) from exc

    return BuildDefinition(
        build_type=build_type,
        external_parameters=_external_parameters(job_metadata),
        internal_parameters=internal_parameters_mapper(job_metadata),
        resolved_dependencies=_resolved_dependencies(context),
    )


def run_details_from_context(context: ProvenanceContext) -> RunDetails:
    """Map a ``ProvenanceContext`` to SLSA ``RunDetails``."""
    return RunDetails(
        builder=BuilderIdentity(id=context.builder_id),
        metadata=BuildMetadata(
            invocation_id=context.invocation_id,
            started_on=context.started_at,
            finished_on=context.finished_at,
        ),
    )


# ---------------------------------------------------------------------------
# Predicate -> dict (SLSA v1 JSON shape)
# ---------------------------------------------------------------------------


def resource_descriptor_to_dict(descriptor: ResourceDescriptor) -> dict[str, object]:
    """Map a ``ResourceDescriptor`` to its in-toto JSON shape.

    Delegates to ``ResourceDescriptor.to_dict()``.
    """
    return descriptor.to_dict()


def builder_identity_to_dict(builder: BuilderIdentity) -> dict[str, object]:
    """Map a ``BuilderIdentity`` to its SLSA v1 JSON shape."""
    result: dict[str, object] = {"id": builder.id}
    if builder.version is not None:
        result["version"] = dict(builder.version)
    if builder.builder_dependencies:
        result["builderDependencies"] = [
            resource_descriptor_to_dict(dependency) for dependency in builder.builder_dependencies
        ]
    return result


def build_definition_to_dict(build_definition: BuildDefinition) -> dict[str, object]:
    """Map a ``BuildDefinition`` to its SLSA v1 JSON shape."""
    result: dict[str, object] = {
        "buildType": build_definition.build_type,
        "externalParameters": dict(build_definition.external_parameters),
        "internalParameters": dict(build_definition.internal_parameters),
    }
    if build_definition.resolved_dependencies:
        result["resolvedDependencies"] = [
            resource_descriptor_to_dict(dependency)
            for dependency in build_definition.resolved_dependencies
        ]
    return result


def run_details_to_dict(run_details: RunDetails) -> dict[str, object]:
    """Map ``RunDetails`` to its SLSA v1 JSON shape."""
    result: dict[str, object] = {
        "builder": builder_identity_to_dict(run_details.builder),
        "metadata": run_details.metadata.to_dict(),
    }
    if run_details.byproducts:
        result["byproducts"] = [
            resource_descriptor_to_dict(byproduct) for byproduct in run_details.byproducts
        ]
    return result


def predicate_to_dict(predicate: SLSAProvenancePredicate) -> dict[str, object]:
    """Map a ``SLSAProvenancePredicate`` to the SLSA v1 ``predicate`` JSON shape.

    The result is suitable for writing directly as ``predicate.json`` (it
    does not include an in-toto ``Statement`` wrapper or ``predicateType``).
    """
    return {
        "buildDefinition": build_definition_to_dict(predicate.build_definition),
        "runDetails": run_details_to_dict(predicate.run_details),
    }


__all__ = [
    "build_definition_from_context",
    "build_definition_to_dict",
    "builder_identity_to_dict",
    "predicate_to_dict",
    "resource_descriptor_from_artifact",
    "resource_descriptor_from_git_metadata",
    "resource_descriptor_to_dict",
    "run_details_from_context",
    "run_details_to_dict",
]

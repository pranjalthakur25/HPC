"""Use case: generate an in-toto/SLSA provenance statement for a job."""

from __future__ import annotations

from dataclasses import dataclass

from hpc_provenance.application.dto.requests import GenerateProvenanceRequest
from hpc_provenance.domain.enums import ArtifactRole
from hpc_provenance.domain.interfaces.clock import Clock
from hpc_provenance.domain.interfaces.collectors import (
    ArtifactMetadataCollector,
    GitMetadataCollector,
    SchedulerMetadataCollector,
)
from hpc_provenance.domain.interfaces.provenance import (
    InTotoStatementBuilder,
    ProvenancePredicateBuilder,
)
from hpc_provenance.domain.models.in_toto import InTotoStatement
from hpc_provenance.domain.models.provenance_context import ProvenanceContext
from hpc_provenance.infrastructure.provenance.slsa_predicate_mapper import (
    resource_descriptor_from_artifact,
)


@dataclass(frozen=True, slots=True)
class GenerateProvenanceUseCase:
    """Collects job/source/artifact metadata and assembles an in-toto
    Statement carrying a SLSA provenance predicate.

    All dependencies are ports (``Protocol``s) -- this class never imports a
    concrete adapter. See ``config.container.Container`` for wiring and
    ``ARCHITECTURE.md`` section 7.1 for the sequence diagram.
    """

    git_collector: GitMetadataCollector
    scheduler_collector: SchedulerMetadataCollector
    artifact_collector: ArtifactMetadataCollector
    predicate_builder: ProvenancePredicateBuilder
    statement_builder: InTotoStatementBuilder
    clock: Clock

    def execute(self, request: GenerateProvenanceRequest) -> InTotoStatement:
        """Run the generate-provenance flow.

        Steps:
            1. Resolve ``request.job_id`` via ``scheduler_collector``.
            2. Collect git metadata via ``git_collector`` (if
               ``request.git_repository_path`` is set).
            3. Collect material/product artifacts via ``artifact_collector``.
            4. Assemble a ``ProvenanceContext`` from the above plus
               ``clock.now()``.
            5. Build a ``SLSAProvenancePredicate`` via ``predicate_builder``.
            6. Build and return an ``InTotoStatement`` via
               ``statement_builder``.

        Raises:
            MetadataCollectionError: propagated from collectors.
            ProvenanceGenerationError: propagated from builders.
        """
        job_metadata = self.scheduler_collector.collect(request.job_id)

        git_metadata = (
            self.git_collector.collect(request.git_repository_path)
            if request.git_repository_path is not None
            else None
        )

        materials = self.artifact_collector.collect(request.material_paths, ArtifactRole.MATERIAL)
        products = self.artifact_collector.collect(request.product_paths, ArtifactRole.PRODUCT)

        window = job_metadata.execution_window
        context = ProvenanceContext(
            job_metadata=job_metadata,
            materials=materials,
            products=products,
            builder_id=request.builder_id,
            invocation_id=str(job_metadata.job_id),
            started_at=window.started_at or self.clock.now(),
            git_metadata=git_metadata,
            finished_at=window.finished_at,
        )

        predicate = self.predicate_builder.build(context)
        subjects = tuple(resource_descriptor_from_artifact(product) for product in products)
        return self.statement_builder.build(
            subjects, self.predicate_builder.predicate_type, predicate
        )

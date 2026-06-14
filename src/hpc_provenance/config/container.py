"""Composition root: wires concrete infrastructure adapters into use cases
based on ``Settings``.

This is the *only* module that imports both domain ports and concrete
infrastructure classes -- nothing else in this codebase should construct an
infrastructure adapter directly.
"""

from __future__ import annotations

from functools import cached_property

from hpc_provenance.application.services.slurm_provenance_service import SlurmProvenanceService
from hpc_provenance.application.use_cases.generate_provenance import GenerateProvenanceUseCase
from hpc_provenance.application.use_cases.sign_provenance import SignProvenanceUseCase
from hpc_provenance.application.use_cases.verify_provenance import VerifyProvenanceUseCase
from hpc_provenance.config.settings import Settings
from hpc_provenance.domain.enums import SchedulerType
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
from hpc_provenance.domain.interfaces.repositories import KeyRepository, ProvenanceRepository
from hpc_provenance.domain.interfaces.signing import DSSEEnvelopeSigner, DSSEEnvelopeVerifier
from hpc_provenance.infrastructure.clock import SystemClock
from hpc_provenance.infrastructure.collectors.artifact_collector import FilesystemArtifactCollector
from hpc_provenance.infrastructure.collectors.git_collector import GitPythonMetadataCollector
from hpc_provenance.infrastructure.collectors.slurm_collector import (
    SlurmCliMetadataCollector,
    SlurmEnvMetadataCollector,
)
from hpc_provenance.infrastructure.provenance.in_toto_statement_builder import (
    InTotoV1StatementBuilder,
)
from hpc_provenance.infrastructure.provenance.slsa_predicate_builder import SLSAv1PredicateBuilder
from hpc_provenance.infrastructure.repositories.filesystem_provenance_repository import (
    FilesystemProvenanceRepository,
)
from hpc_provenance.infrastructure.repositories.local_key_repository import LocalFileKeyRepository
from hpc_provenance.infrastructure.signing.dsse_signer import DsseSigner
from hpc_provenance.infrastructure.signing.dsse_verifier import DsseVerifier
from hpc_provenance.infrastructure.signing.payload_signers import create_payload_signer
from hpc_provenance.shared.errors import ConfigurationError


class Container:
    """Composition root.

    Adapters are constructed lazily and cached for the lifetime of this
    ``Container`` (one instance per CLI invocation). Use cases are
    constructed fresh on each call, wiring in the cached adapters.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ------------------------------------------------------------------
    # Adapters
    # ------------------------------------------------------------------

    @cached_property
    def clock(self) -> Clock:
        return SystemClock()

    @cached_property
    def git_collector(self) -> GitMetadataCollector:
        return GitPythonMetadataCollector()

    @cached_property
    def scheduler_collector(self) -> SchedulerMetadataCollector:
        match self._settings.scheduler_type:
            case SchedulerType.SLURM:
                return SlurmCliMetadataCollector()
            case other:
                raise ConfigurationError(f"Unsupported scheduler_type: {other!r}")

    @cached_property
    def slurm_env_collector(self) -> SchedulerMetadataCollector:
        """Environment-variable-based collector for prologue/epilogue hooks
        (as opposed to ``scheduler_collector``, which shells out to
        ``sacct``/``scontrol`` for ``generate run``).
        """
        return SlurmEnvMetadataCollector()

    @cached_property
    def artifact_collector(self) -> ArtifactMetadataCollector:
        return FilesystemArtifactCollector(digest_algorithm=self._settings.digest_algorithm)

    @cached_property
    def predicate_builder(self) -> ProvenancePredicateBuilder:
        return SLSAv1PredicateBuilder()

    @cached_property
    def statement_builder(self) -> InTotoStatementBuilder:
        return InTotoV1StatementBuilder()

    @cached_property
    def envelope_signer(self) -> DSSEEnvelopeSigner:
        return DsseSigner()

    @cached_property
    def envelope_verifier(self) -> DSSEEnvelopeVerifier:
        return DsseVerifier()

    @cached_property
    def provenance_repository(self) -> ProvenanceRepository:
        return FilesystemProvenanceRepository(root_directory=self._settings.output_directory)

    @cached_property
    def key_repository(self) -> KeyRepository:
        return LocalFileKeyRepository(
            keys_directory=self._settings.keys_directory,
            trusted_key_ids_override=self._settings.trusted_key_ids,
        )

    # ------------------------------------------------------------------
    # Use cases
    # ------------------------------------------------------------------

    def generate_provenance_use_case(self) -> GenerateProvenanceUseCase:
        return GenerateProvenanceUseCase(
            git_collector=self.git_collector,
            scheduler_collector=self.scheduler_collector,
            artifact_collector=self.artifact_collector,
            predicate_builder=self.predicate_builder,
            statement_builder=self.statement_builder,
            clock=self.clock,
        )

    def sign_provenance_use_case(self) -> SignProvenanceUseCase:
        return SignProvenanceUseCase(
            envelope_signer=self.envelope_signer,
            key_repository=self.key_repository,
            provenance_repository=self.provenance_repository,
            payload_signer_factory=create_payload_signer,
        )

    def verify_provenance_use_case(self) -> VerifyProvenanceUseCase:
        return VerifyProvenanceUseCase(
            envelope_verifier=self.envelope_verifier,
            key_repository=self.key_repository,
            provenance_repository=self.provenance_repository,
        )

    def slurm_provenance_service(self) -> SlurmProvenanceService:
        generate_use_case = GenerateProvenanceUseCase(
            git_collector=self.git_collector,
            scheduler_collector=self.slurm_env_collector,
            artifact_collector=self.artifact_collector,
            predicate_builder=self.predicate_builder,
            statement_builder=self.statement_builder,
            clock=self.clock,
        )
        return SlurmProvenanceService(
            scheduler_collector=self.slurm_env_collector,
            git_collector=self.git_collector,
            generate_use_case=generate_use_case,
            sign_use_case=self.sign_provenance_use_case(),
        )

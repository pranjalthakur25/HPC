"""Infrastructure layer: adapters implementing domain ports.

Depends on ``hpc_provenance.domain`` (and DTOs from
``hpc_provenance.application``) plus external libraries (GitPython,
cryptography, ...). Concrete classes here are selected and wired together
only by ``hpc_provenance.config.container.Container``.
"""

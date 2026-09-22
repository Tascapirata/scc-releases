# SCC Runner Releases

Public distribution channel for SCC Runner installation artifacts.

This repository is intentionally separate from the private SCC source
repository. It exists only to publish release artifacts intended for
external installation.

Published SCC releases may contain:

- `scc_runner-<version>-py3-none-any.whl`
- `SHA256SUMS`
- `release-manifest.json`

Consumers should install only from an explicitly identified published
release. Repository branch snapshots and automatically generated source
archives are not SCC Runner installation packages.

Published releases use GitHub release immutability. SCC additionally
verifies its own manifest, checksums and wheel metadata before
activation.

This repository does not claim public source reproducibility or
independent code signing.

---

## Español

Canal público de distribución para los artefactos de instalación de
SCC Runner.

Este repositorio está separado deliberadamente del repositorio privado
del código fuente de SCC. Su única función es publicar artefactos de
release destinados a instalación externa.

Las releases de SCC pueden contener:

- `scc_runner-<version>-py3-none-any.whl`
- `SHA256SUMS`
- `release-manifest.json`

Sólo deben instalarse artefactos procedentes de una release publicada
e identificada explícitamente. Las copias de ramas y los archivos de
código fuente generados automáticamente por GitHub no son paquetes de
instalación de SCC Runner.

Las releases publicadas utilizan inmutabilidad de GitHub. SCC verifica
además su propio manifiesto, checksums y metadatos del wheel antes de
activar una instalación.

Este repositorio no afirma reproducibilidad pública desde el código
fuente ni firma de código independiente.

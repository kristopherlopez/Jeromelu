# GPU Service Instructions

Read this before editing `services/gpu/**`.

## Scope

`services/gpu` holds GPU/SageMaker runtime code. It is intentionally isolated from the API and unit-test import paths.

## Required Context

- Service setup: `services/gpu/SETUP.md`
- Terraform GPU/IAM shape: `infra/terraform/lineup.tf`
- Invariant: `docs/build/META.md#heavy-ml-deps-stay-isolated`
- Tests: `tests/unit/gpu/`

## Rules

- Do not import GPU-only dependencies from API, shared, or unit-test collection paths.
- Keep deploy helper changes covered by lightweight tests where possible.
- SageMaker endpoint/model/config changes must stay aligned with Terraform-owned ECR/S3/IAM resources.
- Do not add new AWS resources from scripts as a shortcut; Terraform owns infrastructure.
- Treat model files and large binaries as external artifacts, not repo contents.

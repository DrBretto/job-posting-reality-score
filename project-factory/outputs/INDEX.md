# Outputs Index

This directory stores canonical artifact roots produced or managed by the factory.

## Layout Rules

- Register each artifact root in `REGISTRY.tsv`.
- Each artifact root should include:
  - `START_HERE.md`
  - `CURRENT_STATUS.md`
  - `runs/<run_id>_<label>/...`
- Keep run directories immutable once checkpointed; create a new run for revisions.
- Use exact paths in packets and manifests.

## Seeded Artifact Roots

- `factory-system-bootstrap/` - initial factory bootstrap and validation artifacts for this template repo
- `template-ops-playbook/` - template maintenance/process-ops outputs and packaging run artifacts

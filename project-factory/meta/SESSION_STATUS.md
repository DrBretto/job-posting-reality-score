# SESSION_STATUS

## Current Session Snapshot

- updated_at: 2026-08-02
- session_state: AWAITING_REAL_JOB_RADAR_DEPLOYMENT_APPROVAL
- what_moved: Replaced placeholder targets locally and connected fit ranking, linked reporting, and
  SES delivery to the deployed pipeline's data model.
- blocked: No technical blocker. AWS deployment and SSM update require explicit operator approval.
- what_is_next: Review the feature-branch result, then approve or decline the controlled deployment.
- exact_artifact_paths:
  - `START_HERE.md`
  - `docs/plans/2026-08-02-real-job-radar.md`
  - `config/companies.yaml`
  - `src/scoring/scoring.py`
  - `src/report/handler.py`
  - `infra/DEPLOY.md`
- next_unlocked_task: No AWS action until Brett approves the deployment checkpoint.

## Verified Boundaries

- Production remains on the original three targets until explicit deployment approval.
- Deploy code before replacing `/jprs/companies`, and never change the registry during a run.
- Bedrock and Ashby remain off.
- No automated applications or personal-contact harvesting.
- Never record private account identifiers, ARNs, keys, MFA codes, or notification addresses.

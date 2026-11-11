"""Independent P08 review: refuse the first pending-ledger write, then change the feed window."""

import json
from pathlib import Path


original = Path(
    "project-factory/outputs/open-market-discovery/runs/"
    "20260925_discovery_to_report_integration_v1/evidence/"
    "p07_independent_interrupted_publish_probe.py"
).read_text()
source = original.replace(
    '== s3layout.discovery_live_key("himalayas")',
    '== s3layout.discovery_pending_publication_key()',
).replace(
    'raise TimeoutError("review-injected storage failure before live-view commit")',
    'raise TimeoutError("review-injected failure of FIRST pending-ledger PutObject")',
).replace(
    'first_coverage = read_json(storage, s3layout.discovery_coverage_key(first_run))',
    'first_coverage = {"discovery_succeeded": "not reached in this probe"}',
).replace(
    'state_before_retry = read_json(storage, s3layout.discovery_state_key())',
    'state_before_retry = {"not_checked": True}',
).replace(
    '"traversal_state_persisted_before_live_commit": bool(state_before_retry),',
    '"traversal_state_persisted_before_live_commit": "not checked",',
).replace(
    '"real P07 producers/consumers with external AWS/HTTP mocked; one external storage failure and a changed feed window; no test-created intermediates"',
    '"P08 working tree, real producers/consumers, external AWS/HTTP mocked; first pending-ledger write fails once; no test-created intermediates"',
)
assert source != original
namespace = {"__name__": "p08_independent_probe"}
exec(compile(source, "p08_adapted_p07_probe", "exec"), namespace)
result = {
    "control": namespace["run_probe"](False),
    "first_pending_write_failed": namespace["run_probe"](True),
}
print(json.dumps(result, indent=2))

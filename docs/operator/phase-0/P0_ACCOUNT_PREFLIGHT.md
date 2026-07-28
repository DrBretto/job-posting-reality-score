# P0 Account Preflight

**Observed:** 2026-07-28

**Method:** read-only AWS inspection

**AWS resources changed:** none

This file intentionally omits account numbers, ARNs, access-key IDs, and contact details.

## Already True

- The configured CLI region is `us-east-1`.
- The active caller is a non-root IAM user.
- Root-user MFA is enabled.
- An AWS Budget and a CloudWatch billing alarm already exist for unrelated account-wide monitoring.

These facts do not complete P0. The existing cost controls use different thresholds and the billing
alarm is not receiving data.

## Action Required

### 1. Root Access Key Exists

The account summary reports an active root-user access key. Root access keys should not exist unless
there is an exceptional, documented dependency.

Manually inspect its last-used information. Identify any dependent workload before disabling it.
Delete it after confirming that nothing relies on it. Do not rotate it into another root key.

### 2. Human IAM User Has No MFA

The current non-root IAM user has no MFA device. It also carries administrator access. Add MFA before
using it for project work. IAM Identity Center is the preferred longer-term human access path, but
MFA on the current user is the fastest P0-compatible correction.

### 3. Long-Lived Access Key Needs Inventory

The current IAM user has one active access key created on 2025-06-25. Do not delete it blindly:
inventory local tools, scripts, and deployed workloads that use its profile, then migrate or rotate it
without breaking existing work.

### 4. Billing Metrics Are Not Arriving

The existing `$20` CloudWatch billing alarm has been `INSUFFICIENT_DATA` since January 2026, and no
`AWS/Billing` `EstimatedCharges` metric is currently visible. Enable CloudWatch billing alerts in
Billing preferences before creating the project alarm. The first metric may take time to appear.

### 5. Existing Budget Is Not the Project Fence

The existing account budget does not implement the JPRS `$5` warning thresholds and `$10` emergency
ceiling. Create project-named controls so their purpose is obvious.

### 6. IAM Access Analyzer Is Not Enabled

No account-level Access Analyzer exists in `us-east-1`. Create one and confirm there are no unintended
external-access findings relevant to the project.

## P0 Gate Status

**NOT COMPLETE.** Continue with `P0_CONSOLE_WORKSHEET.md`. P1 remains locked until the manual actions,
shared verification, and no-notes recall answer all pass.

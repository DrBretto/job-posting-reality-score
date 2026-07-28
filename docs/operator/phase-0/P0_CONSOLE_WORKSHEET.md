# P0 Console Worksheet

Use the AWS console for every action in this worksheet. The point is to rebuild the menu and service
relationships in memory, so do not replace these steps with a deployment script.

Do not paste account numbers, ARNs, access-key IDs, MFA codes, or personal email addresses into this
repository.

## 0. Fill In

| Item | Your entry |
|---|---|
| Date started | `____________` |
| Console region | `us-east-1` |
| Human principal used | `____________` (name only; no ARN) |
| Notification destination verified | `[ ]` |

## 1. Secure Root and Human Access

### Root user

- [ ] Sign in as root only for this review.
- [ ] Open **Security credentials** and confirm MFA is enabled.
- [ ] Inspect the existing root access key's last-used information.
- [ ] Identify any dependency before changing the key.
- [ ] Disable, verify, then delete the root key if it is unused.
- [ ] Sign out of root.

Observation, without private identifiers:

`______________________________________________________________________________`

### Daily human identity

- [ ] Sign in as the normal non-root user.
- [ ] Add an MFA device to that user.
- [ ] Record which local tools or workloads depend on its existing long-lived access key.
- [ ] Plan a safe migration/rotation; do not break an unidentified dependency for the exercise.

Dependency inventory:

`______________________________________________________________________________`

## 2. Enable Billing Alerts

Path:

**Billing and Cost Management -> Billing preferences -> Alert preferences**

- [ ] Enable **Receive CloudWatch billing alerts**.
- [ ] Save preferences.
- [ ] Note the time: `____________`.
- [ ] Allow time for the first `EstimatedCharges` metric to appear.

This account currently has a billing alarm with no data. Creating another alarm before enabling this
preference would reproduce the same broken state.

## 3. Intentional Failure: Wrong Region

This is the P0 failure-recall exercise.

- [ ] Open CloudWatch in any region other than `us-east-1`.
- [ ] Start creating an alarm and look for `Billing -> Total Estimated Charge`.
- [ ] Observe that `EstimatedCharges` is unavailable or empty.
- [ ] Write what you saw: `________________________________________________________`.
- [ ] Return to `us-east-1`.
- [ ] Confirm the billing metric is present there after billing alerts have begun publishing.

Lesson in your words:

`______________________________________________________________________________`

## 4. Create the Project Budgets

Path:

**Billing and Cost Management -> Budgets -> Create budget -> Customize (advanced) -> Cost budget**

### Warning budget

- [ ] Name: `jprs-monthly-warning`
- [ ] Period: Monthly
- [ ] Type: Fixed
- [ ] Amount: `$5.00`
- [ ] Actual alert: 50% (`$2.50`)
- [ ] Actual alert: 80% (`$4.00`)
- [ ] Actual alert: 100% (`$5.00`)
- [ ] Forecasted alert: 80% (`$4.00`)
- [ ] Confirm the notification destination.

### Emergency ceiling

- [ ] Name: `jprs-hard-stop`
- [ ] Period: Monthly
- [ ] Type: Fixed
- [ ] Amount: `$10.00`
- [ ] Add an actual-cost notification at 100%.
- [ ] Do **not** invent a scheduler-disable action in P0.
- [ ] Leave the automatic IAM action pending until the dedicated scheduler role exists in P4.

AWS Budgets is delayed cost telemetry, not an instantaneous circuit breaker. The primary controls are
serverless-only scope, bounded retries/concurrency, finite log retention, and the P4 role lockdown.

## 5. Create the Billing Alarm

Path:

**CloudWatch (`us-east-1`) -> Alarms -> Create alarm -> Select metric -> Billing -> Total Estimated
Charge -> USD**

- [ ] Alarm name: `jprs-billing-5-usd`
- [ ] Statistic: Maximum
- [ ] Period: 6 hours
- [ ] Threshold: Greater than `$5.00`
- [ ] Missing data: treat as missing
- [ ] Connect the verified notification destination.
- [ ] Confirm the alarm is no longer permanently stuck because the source metric is absent.

Initial state and observation:

`______________________________________________________________________________`

## 6. Enable IAM Access Analyzer

Path:

**IAM -> Access Analyzer -> Create analyzer**

- [ ] Name: `jprs-account-analyzer`
- [ ] Analysis type: External access
- [ ] Zone of trust: Current AWS account
- [ ] Region: `us-east-1`
- [ ] Create the analyzer.
- [ ] Review findings and record only the count and disposition, not private resource identifiers.

Finding count and disposition:

`______________________________________________________________________________`

## 7. Create the Execution Boundary

Path:

**IAM -> Policies -> Create policy -> JSON**

- [ ] Open `policies/jprs-execution-boundary.json` locally.
- [ ] Read every statement before pasting it.
- [ ] Create customer-managed policy `jprs-execution-boundary`.
- [ ] Review the generated permissions summary.
- [ ] Do **not** attach it to the human administrator.
- [ ] Record that all future JPRS execution roles must use this as their permissions boundary.

Explain what a permissions boundary does:

`______________________________________________________________________________`

## 8. Prepare the P4 Cost Lockdown Policy

- [ ] Open and inspect `policies/jprs-budget-lockdown-deny.json`.
- [ ] Create customer-managed policy `jprs-budget-lockdown-deny`.
- [ ] Do not attach it manually today.
- [ ] Record the P4 dependency: configure the `$10` Budget Action to attach this policy to the
      dedicated scheduler invocation role.

The policy blocks new scheduler-initiated Lambda, Step Functions, and SQS work. It does not literally
toggle the schedule to Disabled, and cost telemetry can lag.

## 9. Shared Verification

Ask the AI for a read-only P0 verification after completing the console steps.

- [ ] CLI/default region is `us-east-1`.
- [ ] Root MFA remains enabled.
- [ ] Root access key is absent, or an explicit dependency and removal plan are recorded.
- [ ] Normal human user has MFA.
- [ ] `AWS/Billing` `EstimatedCharges` exists in `us-east-1`.
- [ ] `jprs-monthly-warning` is `$5` with 50/80/100 actual and 80 forecast notifications.
- [ ] `jprs-hard-stop` is `$10`.
- [ ] `jprs-billing-5-usd` watches the USD billing metric at `$5`.
- [ ] `jprs-account-analyzer` is active.
- [ ] Both IAM policies exist and match the repository JSON.
- [ ] No JPRS execution resources have been created yet.

## 10. Done Gate

- [ ] All shared verification checks pass.
- [ ] The intentional wrong-region failure was observed.
- [ ] Any unresolved root/access-key dependency is explicitly recorded and time-bounded.
- [ ] You can answer this without notes:

> Why must the billing alarm live in us-east-1, and what is the difference between an AWS Budget and
> a CloudWatch billing alarm?

Answer:

`______________________________________________________________________________`

P0 completed on: `____________`

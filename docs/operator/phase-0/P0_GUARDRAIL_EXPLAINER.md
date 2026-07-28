# P0 Guardrail Explainer

## What Each Control Catches

| Control | Purpose | What it does not do |
|---|---|---|
| `$5` AWS Budget | Tracks aggregate monthly cost against 50%, 80%, and 100% actual thresholds plus 80% forecast | It is not real-time and does not prevent an individual request |
| `$10` ceiling Budget | Triggers the emergency notification and, at P4, applies a lockdown policy to the scheduler role | It cannot directly disable an EventBridge schedule |
| `$5` CloudWatch billing alarm | Watches the account's `EstimatedCharges` metric independently of Budgets | It is reactive, delayed, and only receives the billing metric in `us-east-1` |
| Permissions boundary | Caps the maximum permissions future JPRS execution roles can receive | It grants no permission by itself and is not attached to the human administrator |
| IAM Access Analyzer | Detects resource policies that allow access from outside the account's trust zone | It is not a vulnerability scanner or a substitute for least-privilege role design |
| 30-day log retention | Prevents forgotten CloudWatch logs from accumulating forever | It must be set on each log group; the default is never expire |
| Service exclusions | Prevents starter-scope use of common always-on or unexpectedly expensive services | It does not replace reviewing every architecture change |

## Supported Emergency Lockdown

AWS Budget Actions support applying an IAM policy or Service Control Policy, and limited SSM actions
for stopping EC2 or RDS. They do not provide an action that directly disables EventBridge Scheduler.

For JPRS:

1. P0 creates the inspectable `jprs-budget-lockdown-deny` policy.
2. P4 creates a dedicated scheduler invocation role.
3. P4 configures the `$10` Budget Action to attach the lockdown policy to that role.
4. The deny prevents that role from invoking Lambda, starting Step Functions executions, or sending
   new SQS messages.
5. Manual response still includes inspecting spend and disabling the schedules in the console.

This is a backstop, not an instantaneous fuse. AWS cost data and Budget evaluation can lag. The
stronger first-line controls are no always-on infrastructure, finite retry paths, reserved Lambda
concurrency, finite logs, and deliberately small schedules.

## Threshold Memo

| Control | Setting |
|---|---|
| Warning budget | `$5/month`, fixed |
| Warning alerts | 50%, 80%, 100% actual; 80% forecast |
| Emergency budget | `$10/month`, fixed |
| Billing alarm | Greater than `$5`, Maximum, 6-hour period, USD |
| Log retention | 30 days for every Lambda and Step Functions log group |
| Starter target | Less than `$5/month` under expected use |

## References

- AWS CloudWatch billing alarms:
  https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/monitor_estimated_charges_with_cloudwatch.html
- AWS Budgets Actions:
  https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-controls.html
- AWS CLI Budget Action action types:
  https://docs.aws.amazon.com/cli/latest/reference/budgets/create-budget-action.html
- IAM root-user best practices:
  https://docs.aws.amazon.com/IAM/latest/UserGuide/root-user-best-practices.html
- IAM best practices:
  https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html

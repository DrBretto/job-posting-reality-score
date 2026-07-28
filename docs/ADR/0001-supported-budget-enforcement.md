# ADR 0001: Supported Budget Enforcement

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

The committee's M5 condition correctly requires a cost fence that does more than notify. Its proposed
mechanism says an AWS Budget Action should directly disable the EventBridge Scheduler schedule.

AWS Budget Actions do not expose that operation. Their supported enforcement paths are applying an
IAM policy or Service Control Policy, plus limited SSM actions to stop EC2 or RDS instances. Treating
direct scheduler disablement as available would make the P0 worksheet unexecutable and teach an
incorrect AWS capability.

Budget evaluation also depends on delayed cost data. No Budget Action should be described as an
instantaneous circuit breaker.

## Decision

1. Create a customer-managed `jprs-budget-lockdown-deny` policy during P0.
2. Create a dedicated scheduler invocation role during P4.
3. Configure the `$10` Budget Action during P4 to attach the lockdown policy automatically to that
   role.
4. Deny scheduler-initiated `lambda:InvokeFunction`, `states:StartExecution`, and `sqs:SendMessage`
   calls for JPRS resources.
5. Keep manual schedule disablement as an incident-response step.
6. Keep no-always-on services, bounded retries/concurrency, and finite log retention as the primary
   preventive cost controls.

## Consequences

- The committee's cost-enforcement objective remains intact through a supported AWS mechanism.
- New scheduled work is blocked after the policy action takes effect, even though the schedule's
  visual state remains Enabled.
- In-flight requests and unrelated account spending are not stopped.
- The action cannot be fully configured in P0 because its target role does not exist until P4.
- Cost telemetry lag means a fast spike may pass `$10` before enforcement occurs.

## Alternatives Considered

An SNS notification invoking a separate Lambda that disables EventBridge schedules would mirror the
desired console state more literally. It was rejected for V1 because it adds another function, role,
failure path, and control that must itself be tested. Revisit only if the IAM lockdown proves
insufficient.

## Sources

- https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-controls.html
- https://docs.aws.amazon.com/cli/latest/reference/budgets/create-budget-action.html
- https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html

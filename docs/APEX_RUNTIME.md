# Catalyst Apex Runtime v3

Apex is Catalyst's top-level mission contract and routing layer. It coordinates existing subsystems without replacing their execution authorities.

## Mission contract

Each mission contains:

- objective and durable mission identity
- objective type and structured reasoning plan
- capability envelope
- evidence and verification requirements
- risk and uncertainty budgets
- governance requirements
- durable checkpoints and lifecycle events

## Routing

Apex normalizes reasoning objective types and selects a registered handler. A handler is explicit, callable, and owned by the host runtime. No model output can register itself as an execution authority.

Current core registration includes the engineering production factory. Other domains can be registered by the deployment host when they have concrete, policy-bound execution adapters.

## Lifecycle

`planned → queued → running → completed`

Failure, pause and cancellation are persisted terminal/non-terminal states as appropriate. Handler results are interpreted rather than blindly translated into `completed`.

## Evidence

Execution outcomes are written into the mission's persisted reasoning evidence, preserving the distinction between a model suggestion and an observed subsystem result.

## Security boundary

Apex planning is not approval. Consequential execution still requires the existing Catalyst policy and creator-approval boundary. Device execution additionally requires per-device authentication.

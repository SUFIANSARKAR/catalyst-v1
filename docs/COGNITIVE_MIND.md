# Catalyst Unified Cognitive Mind — v3.9

Catalyst now has a continuous cognitive state layer connecting durable memory, working memory, world model, situational awareness, missions and turn outcomes.

## Lifecycle

`before_turn -> recall -> reason/act -> observe -> verify -> after_turn -> remember experience`

The cognitive loop is deliberately conservative: ordinary conversation is recorded as experience, not automatically promoted to permanent fact. Explicit memory statements remain authoritative through `CatalystMind`.

## Persistent layers

- `CatalystMind`: explicit durable facts, preferences, decisions, commitments, goals and episodes.
- `WorkingMemory`: bounded current-session working buffer.
- `CognitiveStateStore`: persistent focus, objectives and experience episodes.
- `WorldModel`: temporal entity/relation state.
- `SituationalEngine`: events, proactive suggestions and live context.

Together these form one cognitive context for Catalyst rather than isolated databases.

## Safety

The cognitive state stores data and experience. It does not grant device permissions, bypass approval gates, or auto-execute consequential actions.

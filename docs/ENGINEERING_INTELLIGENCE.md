# Engineering Intelligence

Catalyst treats engineering/scientific compute as an optional specialist capability.

## Design

`Catalyst Mind -> engineering router -> optional PhysicsNeMo/PyVista runtime -> artifacts/provenance`

PhysicsNeMo is used as a source of physics-AI workflow patterns and optional runtime capability. PyVista is used as the optional 3D/mesh inspection and visualization bridge.

Neither dependency is required for normal chat, memory, missions, device control, or the core runtime.

## Safety

Model suitability is never inferred merely because a capability exists. Engineering jobs should record assumptions, units, input data, model configuration, validation evidence, and uncertainty before conclusions are presented as engineering results.

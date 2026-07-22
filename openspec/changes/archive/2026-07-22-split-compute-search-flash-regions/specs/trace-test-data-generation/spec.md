## MODIFIED Requirements

### Requirement: Generated traces include all four primary request families with legal address domains

The generator SHALL emit at least one `read`, `write`, `search`, and `compute` command in the same trace. Random-access `read` and `write` commands MUST stay below `COMPUTE_BASE_LHA`; `compute` commands MUST stay inside the compute region; and `search` commands MUST stay inside the search region implied by the current event-driven runtime geometry.

#### Scenario: Random-access and CIM requests stay in-bounds

- **WHEN** the generator writes the final trace
- **THEN** every `read` and `write` entry MUST target the random-access region, every `compute` entry MUST target the compute region, and every `search` entry MUST target the search region

#### Scenario: All primary request families are present

- **WHEN** the generator writes the final trace
- **THEN** the trace MUST contain at least one entry of type `read`, one of type `write`, one of type `search`, and one of type `compute`

# Trace Test Data Generation Specification

## Purpose

Define the repository-provided script and constraints for generating topology-aware engine trace fixtures used by simulator regression tests.

## Requirements

### Requirement: Repository provides a topology-aware engine trace generator
The repository SHALL provide a script under `test_script/` that generates an event-driven engine trace file at `test_case/test_trace.json` by default. The script MUST accept an explicit output path and an explicit random seed so the generated fixture can be reproduced.

#### Scenario: Default output path is used
- **WHEN** a contributor runs the generator without overriding the output path
- **THEN** the repository MUST write a valid engine-trace JSON array to `test_case/test_trace.json`

#### Scenario: Same seed reproduces the same trace
- **WHEN** a contributor runs the generator twice with the same seed and the same preconditioning input
- **THEN** the generated trace content MUST be byte-for-byte identical

### Requirement: Generated READ requests cover both preconditioned and freshly written data
The generator SHALL derive some random-access `read` requests from records already materialized by `pre_data/precondition_data.json`, and it SHALL also include at least one `read` that targets data written earlier in the same generated trace.

#### Scenario: READ targets preconditioned flash content
- **WHEN** the generator selects a preconditioned record whose `valid_bitmap` marks one or more sectors as valid
- **THEN** it MUST emit at least one `read` request whose `start_lha` and `size` overlap those valid sectors for that record

#### Scenario: READ follows a generated WRITE
- **WHEN** the generator emits a random-access `write` request for a logical address range
- **THEN** the generated trace MUST contain a later `read` request that overlaps at least part of that written range

### Requirement: Generated traces include all four primary request families with legal address domains
The generator SHALL emit at least one `read`, `write`, `search`, and `compute` command in the same trace. Random-access `read` and `write` commands MUST stay below `COMPUTE_BASE_LHA`; `compute` commands MUST stay inside the compute region; and `search` commands MUST stay inside the search region implied by the current event-driven runtime geometry.

#### Scenario: Random-access and CIM requests stay in-bounds
- **WHEN** the generator writes the final trace
- **THEN** every `read` and `write` entry MUST target the random-access region, every `compute` entry MUST target the compute region, and every `search` entry MUST target the search region

#### Scenario: All primary request families are present
- **WHEN** the generator writes the final trace
- **THEN** the trace MUST contain at least one entry of type `read`, one of type `write`, one of type `search`, and one of type `compute`

### Requirement: GC pressure is computed from the current post-preconditioning plane state
The generator SHALL derive its GC-triggering write volume from the current event-driven runtime geometry, `GC_WL_MANAGER_FREE_BLOCK_POOL_THRESHOLD`, and the plane state produced by `Block_Manager.preconditioning(...)`. It MUST choose a target random-access plane and emit enough additional writes on that plane to make the plane eligible for the existing GC path under the current configuration, rather than hard-coding a fixed write count.

#### Scenario: Write count adapts to geometry and threshold
- **WHEN** the current runtime geometry or GC free-block threshold changes
- **THEN** the generator MUST recalculate the required write pressure from those live values instead of reusing a constant request count

#### Scenario: Target plane can enter the existing GC path
- **WHEN** the generator finishes constructing the trace
- **THEN** the trace MUST contain enough target-plane random-access writes that, starting from the current preconditioned state, the target plane can reach `free_block_pool <= GC_WL_MANAGER_FREE_BLOCK_POOL_THRESHOLD` while also having a valid GC victim path available from existing or generated invalid pages

### Requirement: Request families are interleaved whenever dependencies allow
The generator SHALL randomize request ordering with a seeded algorithm, but it MUST preserve causal ordering for dependent pairs such as `write -> read`. When at least one dependency-free request of a different type is available, the generator MUST prefer emitting a different request type over extending the current same-type run.

#### Scenario: Dependency order is preserved
- **WHEN** the trace includes a read-back of a range written earlier in the generated trace
- **THEN** the corresponding `write` entry MUST appear before the dependent `read` entry

#### Scenario: Same-type runs are avoided when alternatives exist
- **WHEN** the generator has at least two dependency-free pending request families available
- **THEN** it MUST choose the next request from a family different from the immediately previous emitted type

### Requirement: The repository uses `test_script/` as the test-script root
The repository SHALL keep the trace generator and the moved regression scripts under `test_script/`, and repository test tooling MUST discover tests from that directory after the rename.

#### Scenario: Test discovery follows the renamed directory
- **WHEN** a contributor runs the repository's configured pytest command after the rename
- **THEN** pytest MUST discover regression files from `test_script/` instead of the old `tests/` path

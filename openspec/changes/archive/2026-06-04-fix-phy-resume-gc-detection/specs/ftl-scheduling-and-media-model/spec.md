## ADDED Requirements

### Requirement: Resumed PHY commands preserve the normal completion-event contract

When `PHY` resumes a suspended write or erase command, it MUST re-enter the simulator through the same completion-event contract used by non-suspended commands. Resume-generated completion events MUST carry `chip_id`, `die_id`, and the original `transactions` batch in a mapping payload that `PHY.execute(...)` can consume without resume-specific branching. Suspending the original command MUST invalidate the superseded in-flight completion event so the resumed command can complete exactly once.

#### Scenario: Resumed write schedules a normal completion event
- **WHEN** a suspended write command is restored on a die and `PHY` schedules its remaining execution time
- **THEN** `PHY` MUST register a `PHY_CHIP_WRITE_COMPLETE` event whose payload includes the resumed command's `chip_id`, `die_id`, and `transactions`

#### Scenario: Resumed erase schedules a normal completion event
- **WHEN** a suspended erase command is restored on a die and `PHY` schedules its remaining execution time
- **THEN** `PHY` MUST register a `PHY_CHIP_ERASE_COMPLETE` event whose payload includes the resumed command's `chip_id`, `die_id`, and `transactions`

#### Scenario: Suspend invalidates the superseded completion event
- **WHEN** a write or erase command is suspended after its original chip-completion event has already been scheduled
- **THEN** `PHY` MUST mark the superseded completion event ignored before scheduling the resumed completion event

### Requirement: Resumed GC writes preserve GC-aware chip classification

When a suspended write command is resumed, `PHY` MUST determine whether it is a GC write from the resumed transaction metadata using the same transaction-type interpretation used by the normal write path. A resumed `GC_WRITE` MUST restore `ChipStatus.GC_WRITE`, while non-GC writes MUST restore `ChipStatus.WRITE`, and the resume path MUST NOT throw a type error while performing this classification.

#### Scenario: Resume restores GC write chip status
- **WHEN** the resumed command's first transaction is a `GC_WRITE`
- **THEN** `PHY` MUST mark the chip as `ChipStatus.GC_WRITE` and continue scheduling completion normally

#### Scenario: Resume restores user write chip status
- **WHEN** the resumed command's first transaction is a non-GC write such as `USER_WRITE` or `MAPPING_WRITE`
- **THEN** `PHY` MUST mark the chip as `ChipStatus.WRITE` and continue scheduling completion normally

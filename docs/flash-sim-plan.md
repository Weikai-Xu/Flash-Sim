# Cycle-Accurate Flash Simulator

## Goal Description
Implement a cycle-accurate flash simulator that supports storage, search, and compute operations, capable of outputting the execution latency of various commands. The simulator uses a standard NAND Flash timing parameter model and receives command sequences through a JSON trace interface, returning the execution latency for each command.

## Acceptance Criteria

Following TDD philosophy, each criterion includes positive and negative tests for deterministic verification.

- AC-1: Correctly parse JSON trace input commands
  - Positive Tests (expected to PASS):
    - Valid JSON command sequence parsed without errors
    - Required fields (command type, address, parameters) recognized
    - Configurable parameters (timing, parallelism) loaded correctly
  - Negative Tests (expected to FAIL):
    - Invalid JSON syntax raises JSONDecodeError
    - Missing required command type field raises validation error
    - Unknown command type raises unsupported command error

- AC-2: Read operation returns correct latency
  - Positive Tests (expected to PASS):
    - Read command returns latency equal to tR timing parameter
    - Latency is consistent across multiple reads to different addresses
    - Configured timing parameters affect the returned latency
  - Negative Tests (expected to FAIL):
    - Returns zero or negative latency for read operation
    - Returns same latency as write or erase operation
    - Latency does not change when timing parameters are modified

- AC-3: Write operation returns correct latency
  - Positive Tests (expected to PASS):
    - Write command returns latency equal to tPROG timing parameter
    - Write latency differs from read and erase latencies
    - Latency reflects the page program operation time
  - Negative Tests (expected to FAIL):
    - Returns read or erase latency for write operation
    - Returns latency below minimum program time threshold

- AC-4: Erase operation returns correct latency
  - Positive Tests (expected to PASS):
    - Erase command returns latency equal to tBERS timing parameter
    - Erase latency is the longest among read/write/erase operations
    - Block-level address validation works correctly
  - Negative Tests (expected to FAIL):
    - Returns read or write latency for erase operation
    - Returns latency below minimum erase time threshold

- AC-5: Search operation returns correct latency (parallel WL Exact Match)
  - Positive Tests (expected to PASS):
    - Search command returns latency for parallel WL activation
    - Parallel WL count affects latency (from configuration)
    - Exact match search completes without error
    - Search latency is based on read-like sensing operation
  - Negative Tests (expected to FAIL):
    - Returns same latency as single WL read operation when multiple WLs specified
    - Does not account for parallel WL activation overhead
    - Search with invalid WL count raises error

- AC-6: Compute operation returns correct latency (parallel Block MAC)
  - Positive Tests (expected to PASS):
    - Compute command returns latency for parallel Block activation
    - Parallel Block count affects latency (from configuration)
    - MAC accumulation operation returns appropriate latency
    - Compute latency based on parallel bit-line sensing
  - Negative Tests (expected to FAIL):
    - Returns same latency as single Block read operation
    - Does not account for multi-Block MAC accumulation overhead
    - Compute with invalid Block count raises error

## Path Boundaries

### Upper Bound (Maximum Acceptable Scope)
The implementation includes a complete flash simulator with:
- All five operations (read, write, erase, search, compute) fully implemented
- Configurable timing parameters for read (tR), program (tPROG), and erase (tBERS)
- Configurable parallel WL count for search and parallel Block count for compute
- JSON trace input parsing with validation
- JSON output format with detailed latency breakdown per command
- Comprehensive test suite with positive and negative test cases
- Command-line interface for running trace files
- Well-documented Python API for library usage

### Lower Bound (Minimum Acceptable Scope)
The implementation includes a basic flash simulator with:
- Read, write, and erase operations returning correct latencies
- Search operation returning parallel WL search latency
- Compute operation returning parallel Block MAC latency
- Fixed timing parameters matching standard NAND Flash values
- Simple JSON trace parser accepting basic command format
- Simple output showing latency per command

### Allowed Choices
- Can use: Pure Python implementation without external dependencies
- Can use: Python with optional NumPy for numerical operations
- Can use: Class-based architecture with FlashSimulator, FlashChip, and Command classes
- Can use: JSON Schema for command validation
- Cannot use: External simulation frameworks
- Cannot use: C/C++ extensions (pure Python only for portability)

> **Note on Deterministic Designs**: The JSON trace format and command structure are fixed per the draft specification. The timing calculation formula follows standard NAND Flash timing models from MQSim.

## Feasibility Hints and Suggestions

> **Note**: This section is for reference and understanding only. These are conceptual suggestions, not prescriptive requirements.

### Conceptual Approach
```python
# Core class structure
class FlashSimulator:
    def __init__(self, timing_params=None, parallel_params=None):
        self.timing = timing_params or default_timing()
        self.parallel = parallel_params or default_parallel()
        self.chip = FlashChip()

    def execute_command(self, cmd: dict) -> dict:
        cmd_type = cmd["type"]
        if cmd_type == "read":
            return self._execute_read(cmd)
        elif cmd_type == "write":
            return self._execute_write(cmd)
        elif cmd_type == "erase":
            return self._execute_erase(cmd)
        elif cmd_type == "search":
            return self._execute_search(cmd)
        elif cmd_type == "compute":
            return self._execute_compute(cmd)

    def run_trace(self, trace: list) -> list:
        return [self.execute_command(cmd) for cmd in trace]

class FlashChip:
    # Simple timing model using lookup table
    TIMING = {
        "read": 75000,      # ns, tR
        "write": 750000,    # ns, tPROG
        "erase": 3800000,   # ns, tBERS
    }
```

### Relevant References
- `MQSim/src/exec/Flash_Parameter_Set.h` - Timing parameter definitions
- `MQSim/src/nvm_chip/flash_memory/Flash_Chip.h` - Flash chip model
- `MQSim/src/nvm_chip/flash_memory/Flash_Chip.cpp:352` - Get_command_execution_latency()
- `MQSim/src/nvm_chip/flash_memory/Flash_Command.h` - Command types
- `MQSim/ssdconfig.xml` - Example configuration format

## Dependencies and Sequence

### Milestones
1. Milestone 1: Project Setup and Configuration
   - Phase A: Create project directory structure
   - Phase B: Implement configuration class for timing and parallel parameters
   - Phase C: Define default NAND Flash timing values (tR=75us, tPROG=750us, tBERS=3.8ms)

2. Milestone 2: Basic Flash Operations
   - Step 1: Implement FlashChip class with timing lookup
   - Step 2: Implement read latency calculation
   - Step 3: Implement write latency calculation
   - Step 4: Implement erase latency calculation

3. Milestone 3: Advanced Flash Operations
   - Section A: Implement search operation with parallel WL support
   - Section B: Implement compute operation with parallel Block support
   - Section C: Add configurable parallel parameters

4. Milestone 4: Trace Interface
   - Step 1: Define JSON command schema
   - Step 2: Implement command parser and validator
   - Step 3: Implement trace runner with latency output

5. Milestone 5: Testing and Documentation
   - Phase A: Write positive and negative test cases
   - Phase B: Create example trace files
   - Phase C: Write usage documentation

All components depend on Milestone 1 (configuration) being completed first.

## Implementation Notes

### Code Style Requirements
- Implementation code and comments must NOT contain plan-specific terminology such as "AC-", "Milestone", "Step", "Phase", or similar workflow markers
- These terms are for plan documentation only, not for the resulting codebase
- Use descriptive, domain-appropriate naming in code instead

--- Original Design Draft Start ---

# Cycle-Accurate Flash Simulator

## Goal
Implement a cycle-accurate flash simulator that supports storage, search, and compute operations, capable of outputting the execution latency of various commands.

## Feature Scope

### 1. Basic Storage Operations
- **Read**: Read data from specified address
- **Write**: Write data to specified address
- **Erase**: Erase data from specified block

### 2. Search Operation (CAM Functionality)
- Simultaneously activate multiple Word Lines (WL)
- Each string's flash cell forms a CAM unit for parallel search
- Output: Search operation latency

### 3. Compute Operation (MAC Functionality)
- Simultaneously activate multiple Blocks
- Use single Word Line (WL)
- Accumulate MAC current on Bit Line (BL)
- Output: Compute operation latency

## Interface
- **Trace Format**: JSON format
- Input: JSON-formatted command sequence
- Output: JSON-formatted latency results

## Timing Model
- Use standard NAND Flash timing parameters (tR, tPROG, tBERS, etc.)
- Parameters are configurable

## Acceptance Criteria
1. Correctly parse JSON trace input
2. Read/write/erase operations return correct latency
3. Search operation returns correct latency (parallel WL search)
4. Compute operation returns correct latency (parallel Block MAC)
5. Latency values conform to standard NAND Flash timing parameters

## Dependencies
- No external dependencies
- Pure Python implementation or optional C extension for Python
--- Original Design Draft End ---

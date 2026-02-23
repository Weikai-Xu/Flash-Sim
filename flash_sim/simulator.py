"""Flash simulator that executes command traces and returns latencies."""

from typing import Optional, List, Dict, Any
from .config import FlashConfig, FlashAddress, FTL
from .chip import FlashChip


class CommandError(Exception):
    """Error raised when a command cannot be executed."""
    pass


class AddressError(Exception):
    """Error raised when address validation fails."""
    pass


class FlashSimulator:
    """Cycle-accurate flash simulator with FTL.

    Executes command sequences and returns latency for each operation.
    Supports read, write, erase, search, and compute operations.

    Architecture:
        Host Command (LBA-based)
            │
            └── FTL (LBA → Physical Address Mapping)
                │
                └── Flash Chip (Timing Calculation)
                    │
                    └── Result (Latency + Physical Address)

    Command Format:
        Read:    {"type": "read",    "lba": 100}
        Write:   {"type": "write",   "lba": 100, "data": ...}
        Erase:   {"type": "erase",   "lba": 100}  # lba → block
        Search:  {"type": "search",  "lba": 100, "wl_count": 8}
        Compute: {"type": "compute", "lba": 100, "block_count": 4, "layer": 0}
    """

    SUPPORTED_COMMANDS = {"read", "write", "erase", "search", "compute"}

    def __init__(self, config: Optional[FlashConfig] = None):
        """Initialize simulator with configuration.

        Args:
            config: Flash configuration. Uses defaults if not provided.
        """
        self.config = config or FlashConfig()
        self.chip = FlashChip(self.config)
        self.ftl = FTL(self.config.geometry)

    def execute_command(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single command and return result with latency.

        Args:
            cmd: Command dictionary with 'type' field and operation-specific parameters.

        Returns:
            Result dictionary containing:
                - 'command': The original command type
                - 'latency_ns': Execution latency in nanoseconds
                - 'status': 'success' or 'error'
                - 'lba': Logical Block Address
                - 'physical_address': Physical flash location
                - Additional fields based on command type

        Raises:
            CommandError: If command type is missing or unsupported.
        """
        if "type" not in cmd:
            raise CommandError("Missing required 'type' field in command")

        cmd_type = cmd["type"]
        if cmd_type not in self.SUPPORTED_COMMANDS:
            raise CommandError(f"Unsupported command type: {cmd_type}")

        handler = getattr(self, f"_execute_{cmd_type}")
        return handler(cmd)

    def _get_lba(self, cmd: Dict[str, Any]) -> int:
        """Get LBA from command, with fallback for backward compatibility."""
        # New format uses 'lba'
        if "lba" in cmd:
            return cmd["lba"]
        # Legacy format uses 'address' or 'block_address'
        if "block_address" in cmd:
            return cmd["block_address"]
        return cmd.get("address", 0)

    def _format_physical_address(self, addr: FlashAddress) -> Dict[str, Any]:
        """Format FlashAddress as dictionary."""
        result = {
            "die": addr.die,
            "plane": addr.plane,
            "block": addr.block,
            "layer": addr.layer,
            "sub_block": addr.sub_block,
            "page_type": addr.page_type,  # LSB=0, CSB=1, MSB=2
        }
        if addr.page >= 0:
            result["page"] = addr.page
        return result

    def _execute_read(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """Execute read command."""
        lba = self._get_lba(cmd)

        # Validate LBA range
        if lba < 0 or lba >= self.ftl._total_lbas:
            raise CommandError(f"Invalid LBA: {lba} out of range [0, {self.ftl._total_lbas})")

        # Get physical address from chip (includes page_type based on technology)
        physical = self.chip.page_to_address(lba)
        latency = self.chip.get_read_latency(lba)

        return {
            "command": "read",
            "lba": lba,
            "address": lba,  # Backward compatibility alias
            "physical_address": self._format_physical_address(physical),
            "latency_ns": latency,
            "status": "success",
        }

    def _execute_write(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """Execute write command."""
        lba = self._get_lba(cmd)

        # Validate LBA range
        if lba < 0 or lba >= self.ftl._total_lbas:
            raise CommandError(f"Invalid LBA: {lba} out of range [0, {self.ftl._total_lbas})")

        # Get physical address from chip (includes page_type based on technology)
        physical = self.chip.page_to_address(lba)
        latency = self.chip.get_write_latency(lba)

        return {
            "command": "write",
            "lba": lba,
            "address": lba,  # Backward compatibility alias
            "physical_address": self._format_physical_address(physical),
            "latency_ns": latency,
            "status": "success",
        }

    def _execute_erase(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """Execute erase command."""
        lba = self._get_lba(cmd)

        # Validate LBA range
        if lba < 0 or lba >= self.ftl._total_lbas:
            raise CommandError(f"Invalid LBA: {lba} out of range [0, {self.ftl._total_lbas})")

        # LBA maps to block for erase (already returns FlashAddress)
        physical = self.ftl.lba_to_block(lba)
        latency = self.chip.get_erase_latency(0)

        # Add page_type=0 for block-level operations
        physical_with_type = FlashAddress(
            die=physical.die,
            plane=physical.plane,
            block=physical.block,
            layer=physical.layer,
            sub_block=physical.sub_block,
            page=-1,
            page_type=0
        )

        return {
            "command": "erase",
            "lba": lba,
            "block_address": lba,  # Backward compatibility alias
            "physical_address": self._format_physical_address(physical_with_type),
            "latency_ns": latency,
            "status": "success",
        }

    def _execute_search(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """Execute search command.

        Search activates multiple Word Lines in parallel within a block.
        The block is determined by the LBA.

        Args:
            cmd: Command with 'lba' and 'wl_count' (number of parallel WLs).
        """
        lba = self._get_lba(cmd)
        wl_count = cmd.get("wl_count", 1)

        try:
            # Get the block containing this LBA
            block_addr = self.ftl.lba_to_block(lba)
        except ValueError as e:
            raise CommandError(f"Invalid LBA: {e}")

        try:
            latency = self.chip.get_search_latency(wl_count)
            return {
                "command": "search",
                "lba": lba,
                "target_block": self._format_physical_address(block_addr),
                "wl_count": wl_count,
                "latency_ns": latency,
                "status": "success",
            }
        except ValueError as e:
            raise CommandError(str(e))

    def _execute_compute(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """Execute compute command.

        Compute activates multiple blocks in parallel for MAC operation.
        Weight data is stored in a specific layer (similar to page).
        The starting block is determined by the LBA.

        Args:
            cmd: Command with 'lba', 'block_count', and 'layer'.
        """
        lba = self._get_lba(cmd)
        block_count = cmd.get("block_count", 1)
        layer = cmd.get("layer", 0)

        try:
            # Get the starting block from LBA
            start_block = self.ftl.lba_to_block(lba)
            # Get all blocks in the range
            block_range = self.ftl.block_range(lba, block_count)
        except ValueError as e:
            raise CommandError(f"Invalid LBA or block count: {e}")

        try:
            latency = self.chip.get_compute_latency(block_count)
            return {
                "command": "compute",
                "lba": lba,
                "start_block": self._format_physical_address(start_block),
                "block_count": block_count,
                "blocks": [self._format_physical_address(b) for b in block_range],
                "layer": layer,
                "latency_ns": latency,
                "status": "success",
            }
        except ValueError as e:
            raise CommandError(str(e))

    def run_trace(self, trace: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute a sequence of commands.

        Args:
            trace: List of command dictionaries.

        Returns:
            List of result dictionaries with latencies.
        """
        results = []
        for cmd in trace:
            try:
                result = self.execute_command(cmd)
                results.append(result)
            except CommandError as e:
                results.append({
                    "command": cmd.get("type", "unknown"),
                    "lba": cmd.get("lba", cmd.get("address", 0)),
                    "latency_ns": 0,
                    "status": "error",
                    "error": str(e),
                })
        return results

    def get_total_latency(self, results: List[Dict[str, Any]]) -> int:
        """Calculate total latency from execution results.

        Args:
            results: List of result dictionaries from run_trace.

        Returns:
            Total latency in nanoseconds.
        """
        return sum(r.get("latency_ns", 0) for r in results)

    def get_wear_info(self) -> Dict[str, int]:
        """Get wear information for all blocks.

        Returns:
            Dictionary with min, max, and average PE counts.
        """
        return self.ftl.get_wear_info()
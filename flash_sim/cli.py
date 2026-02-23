"""Command-line interface for the flash simulator."""

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Optional

from .config import FlashConfig, FlashGeometry, FlashAddress
from .simulator import FlashSimulator
from .parser import parse_trace, format_results, load_config, ParseError, ValidationError


def print_geometry(geo: FlashGeometry) -> None:
    """Print flash geometry information.

    3D NAND model: pages_per_block = layers * sub_blocks
    Each sub-block has 1 page per layer.
    """
    print("\n=== Flash Geometry (3D NAND) ===")
    print(f"  Layers per block:        {geo.layers_per_block}")
    print(f"  Sub-blocks per block:    {geo.sub_blocks_per_block}")
    print(f"  Blocks per plane:        {geo.blocks_per_plane}")
    print(f"  Planes per die:          {geo.planes_per_die}")
    print(f"  Dies:                    {geo.dies}")
    print(f"  ---------------------")
    print(f"  Pages per block:         {geo.pages_per_block}")  # layers * sub_blocks
    print(f"  Pages per layer:         {geo.pages_per_layer}")  # = sub_blocks
    print(f"  Pages per sub-block:     1 (1 page per sub-block/layer)")
    print(f"  Pages per plane:         {geo.pages_per_plane}")
    print(f"  Pages per die:           {geo.pages_per_die}")
    print(f"  Total pages:             {geo.total_pages}")
    print(f"  Total blocks:            {geo.total_blocks}")


def cmd_info(args) -> int:
    """Show flash configuration info."""
    config = load_config_from_args(args)
    print_geometry(config.geometry)
    return 0


def cmd_lba(args) -> int:
    """Convert LBA to physical address."""
    config = load_config_from_args(args)
    geo = config.geometry

    try:
        addr = geo.page_to_address(args.lba)
        print(f"\n=== LBA to Address ===")
        print(f"  LBA:        {args.lba}")
        print(f"  -> Die:      {addr.die}")
        print(f"  -> Plane:    {addr.plane}")
        print(f"  -> Block:    {addr.block}")
        print(f"  -> Layer:    {addr.layer}")
        print(f"  -> SubBlock: {addr.sub_block}")
        print(f"  -> Page:     {addr.page}")

        # Show linear address components
        print(f"\n  LBA per block:  {geo.pages_per_block}")
        print(f"  LBA per die:    {geo.pages_per_die}")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_addr(args) -> int:
    """Convert physical address to LBA."""
    config = load_config_from_args(args)
    geo = config.geometry

    try:
        addr = FlashAddress(
            die=args.die,
            plane=args.plane,
            block=args.block,
            layer=args.layer,
            sub_block=args.sub_block,
            page=args.page
        )
        lba = geo.address_to_page(addr)
        print(f"\n=== Address to LBA ===")
        print(f"  Die:      {args.die}")
        print(f"  Plane:    {args.plane}")
        print(f"  Block:    {args.block}")
        print(f"  Layer:    {args.layer}")
        print(f"  SubBlock: {args.sub_block}")
        print(f"  Page:     {args.page}")
        print(f"  -> LBA:   {lba}")
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_bench(args) -> int:
    """Run benchmark tests."""
    config = load_config_from_args(args)
    sim = FlashSimulator(config)
    geo = config.geometry

    num_ops = args.ops or 1000

    print(f"\n=== Random Read Benchmark ===")
    print(f"  Configuration:")
    print(f"    Layers per block: {geo.layers_per_block}")
    print(f"    Total pages:      {geo.total_pages}")
    print(f"    Operations:       {num_ops}")
    print()

    start = time.perf_counter()

    for _ in range(num_ops):
        lba = random.randint(0, geo.total_pages - 1)
        sim.execute_command({"type": "read", "lba": lba})

    elapsed = time.perf_counter() - start
    avg_latency = (elapsed / num_ops) * 1e6  # in microseconds

    print(f"  Results:")
    print(f"    Total time:   {elapsed:.4f} s")
    print(f"    Avg latency:  {avg_latency:.2f} us")
    print(f"    Throughput:   {num_ops / elapsed:.0f} ops/s")
    return 0


def load_config_from_args(args) -> FlashConfig:
    """Load configuration from args or use defaults."""
    config = FlashConfig()
    if args.config:
        try:
            config_dict = load_config(args.config)
            config = FlashConfig.from_dict(config_dict)
        except ParseError as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            sys.exit(1)
    return config


def cmd_interactive(args) -> int:
    """Run interactive mode."""
    config = load_config_from_args(args)
    sim = FlashSimulator(config)

    print("Flash-Sim Interactive Mode")
    print("=" * 40)
    print_geometry(config.geometry)
    print("\nCommands:")
    print("  read <lba>                  - Read from LBA")
    print("  write <lba>                 - Write to LBA")
    print("  erase <lba>                 - Erase block containing LBA")
    print("  search <lba> <wl_count>     - Search with WL count")
    print("  compute <lba> <block_count> - Compute with block count")
    print("  info                        - Show geometry")
    print("  bench [<ops>]               - Run benchmark")
    print("  quit / exit                 - Exit")
    print()

    while True:
        try:
            line = input("> ").strip()
            if not line:
                continue

            parts = line.split()
            cmd = parts[0].lower()

            if cmd in ("quit", "exit", "q", "x"):
                print("Goodbye!")
                break

            if cmd == "info":
                print_geometry(sim.config.geometry)
                continue

            if cmd == "bench":
                ops = int(parts[1]) if len(parts) > 1 else 1000
                print(f"Running {ops} random reads...")
                start = time.perf_counter()
                for _ in range(ops):
                    lba = random.randint(0, sim.config.geometry.total_pages - 1)
                    sim.execute_command({"type": "read", "lba": lba})
                elapsed = time.perf_counter() - start
                print(f"  {ops} ops in {elapsed:.4f}s ({ops/elapsed:.0f} ops/s)")
                continue

            if cmd == "read" and len(parts) >= 2:
                result = sim.execute_command({"type": "read", "lba": int(parts[1])})
            elif cmd == "write" and len(parts) >= 2:
                result = sim.execute_command({"type": "write", "lba": int(parts[1])})
            elif cmd == "erase" and len(parts) >= 2:
                result = sim.execute_command({"type": "erase", "lba": int(parts[1])})
            elif cmd == "search" and len(parts) >= 3:
                result = sim.execute_command({
                    "type": "search",
                    "lba": int(parts[1]),
                    "wl_count": int(parts[2])
                })
            elif cmd == "compute" and len(parts) >= 3:
                result = sim.execute_command({
                    "type": "compute",
                    "lba": int(parts[1]),
                    "block_count": int(parts[2])
                })
            else:
                print("Invalid command. Type 'help' for available commands.")
                continue

            if result["status"] == "success":
                addr = result["physical_address"]
                print(f"  OK: Die:{addr['die']} Plane:{addr['plane']} "
                      f"Block:{addr['block']} Layer:{addr['layer']} Page:{addr['page']}")
                print(f"  Latency: {result['latency_ns']:,} ns")
            else:
                print(f"  Error: {result.get('error', 'unknown')}")

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

    return 0


def main(argv: Optional[list] = None) -> int:
    """Main entry point for CLI.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    # Use sys.argv[1:] as default if argv is None
    if argv is None:
        argv = sys.argv[1:]

    # Pre-process argv to handle legacy trace file mode
    # If first arg is a file path (looks like .json and exists), treat as legacy mode
    if argv and len(argv) > 0:
        first_arg = argv[0]
        # Check if it's a trace file (not a known command, ends with .json, or file exists)
        if (not first_arg.startswith('-') and
            first_arg not in ['info', 'lba', 'addr', 'run', 'interactive', 'bench', 'help', '--help', '-h'] and
            (first_arg.endswith('.json') or Path(first_arg).exists())):
            # Convert to legacy run mode: insert "run" as first argument
            argv = ['run'] + argv

    parser = argparse.ArgumentParser(
        prog="flash-sim",
        description="Cycle-accurate Flash Simulator with 3D NAND support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show geometry info
  flash-sim info

  # Show geometry with 3D config
  flash-sim info --config my_3d_config.json

  # Convert LBA to physical address
  flash-sim lba 256
  flash-sim lba 256 --config my_3d_config.json

  # Convert physical address to LBA
  flash-sim addr --block 0 --layer 1 --page 100

  # Run a trace file (legacy or new style)
  flash-sim trace.json -o results.json
  flash-sim run trace.json -c my_3d_config.json

  # Interactive mode
  flash-sim interactive -c my_3d_config.json

  # Run benchmark
  flash-sim bench
  flash-sim bench --ops 5000
        """
    )

    parser.add_argument(
        "-c", "--config",
        help="Path to JSON configuration file"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # info command
    info_parser = subparsers.add_parser("info", help="Show flash geometry info")
    info_parser.set_defaults(func=cmd_info)

    # lba command
    lba_parser = subparsers.add_parser("lba", help="Convert LBA to physical address")
    lba_parser.add_argument("lba", type=int, help="Logical Block Address")
    lba_parser.set_defaults(func=cmd_lba)

    # addr command
    addr_parser = subparsers.add_parser("addr", help="Convert physical address to LBA")
    addr_parser.add_argument("--die", type=int, default=0, help="Die index (default: 0)")
    addr_parser.add_argument("--plane", type=int, default=0, help="Plane index (default: 0)")
    addr_parser.add_argument("--block", type=int, required=True, help="Block index")
    addr_parser.add_argument("--layer", type=int, default=0, help="Layer index (default: 0)")
    addr_parser.add_argument("--sub-block", type=int, default=0, help="Sub-block index (default: 0)")
    addr_parser.add_argument("--page", type=int, required=True, help="Page index")
    addr_parser.set_defaults(func=cmd_addr)

    # run command
    run_parser = subparsers.add_parser("run", help="Run a command trace file")
    run_parser.add_argument("trace", help="Path to JSON trace file")
    run_parser.add_argument("-o", "--output", help="Path to output file")
    run_parser.add_argument("--compact", action="store_true", help="Use compact JSON output")
    run_parser.add_argument("--summary", action="store_true", help="Print summary statistics")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    run_parser.set_defaults(func=cmd_run)

    # interactive command
    interactive_parser = subparsers.add_parser("interactive", help="Run in interactive mode")
    interactive_parser.set_defaults(func=cmd_interactive)

    # bench command
    bench_parser = subparsers.add_parser("bench", help="Run benchmark")
    bench_parser.add_argument("--ops", type=int, default=1000, help="Number of operations")
    bench_parser.set_defaults(func=cmd_bench)

    # Add config argument to all subparsers
    for subparser in [info_parser, lba_parser, addr_parser, run_parser, interactive_parser, bench_parser]:
        subparser.add_argument("-c", "--config", help="Path to JSON configuration file")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    return args.func(args)


def cmd_run(args) -> int:
    """Run a command trace."""
    # Load configuration
    config = FlashConfig()
    if args.config:
        try:
            config_dict = load_config(args.config)
            config = FlashConfig.from_dict(config_dict)
            if args.verbose:
                print(f"Loaded config from {args.config}", file=sys.stderr)
        except ParseError as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            return 1

    # Create simulator
    simulator = FlashSimulator(config)

    # Load trace
    try:
        trace = parse_trace(Path(args.trace))
        if args.verbose:
            print(f"Loaded {len(trace)} commands", file=sys.stderr)
    except (ParseError, ValidationError) as e:
        print(f"Error loading trace: {e}", file=sys.stderr)
        return 1

    # Execute trace
    results = simulator.run_trace(trace)

    # Format output
    output = format_results(results, pretty=not args.compact)

    # Write output
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
            f.write("\n")
        if args.verbose:
            print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(output)

    # Print summary if requested
    if args.summary:
        total_latency = simulator.get_total_latency(results)
        success_count = sum(1 for r in results if r.get("status") == "success")
        error_count = len(results) - success_count
        print(f"\n--- Summary ---", file=sys.stderr)
        print(f"Total commands: {len(results)}", file=sys.stderr)
        print(f"Successful: {success_count}", file=sys.stderr)
        print(f"Errors: {error_count}", file=sys.stderr)
        print(f"Total latency: {total_latency:,} ns ({total_latency/1e6:.3f} ms)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
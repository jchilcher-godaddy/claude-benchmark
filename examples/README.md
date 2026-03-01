# Example CLAUDE.md Files

These example CLAUDE.md files demonstrate different levels of configuration for use with claude-benchmark.

## Files

- **minimal.md** -- A bare-bones configuration with basic coding instructions. Good starting point to see how even simple rules affect benchmark scores.
- **comprehensive.md** -- A detailed configuration with specific style, documentation, error handling, and logging rules. Designed to score well across all benchmark task types.

## Usage

Run a benchmark using an example file:

    claude-benchmark run --claudemd examples/comprehensive.md

Or compare two configurations:

    claude-benchmark run --claudemd examples/minimal.md -o results/minimal
    claude-benchmark run --claudemd examples/comprehensive.md -o results/comprehensive
    claude-benchmark report results/minimal results/comprehensive

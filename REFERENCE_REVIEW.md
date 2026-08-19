# Reference Review

The supplied `dravix.py` reference was reviewed for safe reliability and performance patterns before being considered for this tool.

## Decision

No code was copied from the reference. Its core workflow combines a custom encrypted-PAK implementation, crypto material, third-party network/dependency requirements, and a large Rich-based multi-option interface. Those choices are incompatible with this tool's deliberately limited `unpack`, `repack`, and `inject` command set, privacy rules, and Termux performance goals.

The reference's local-directory management and terminal display patterns were also not adopted. They would add filesystem scans, dependencies, and menu features without improving the `repak` backend, which is the primary cost of real PAK work.

## Retained safe approach

The tool continues to use the maintained `repak` executable for authorized PAK operations. Its safe performance improvements remain: a throttled detached update check, streamed Lua-file discovery, and content-only staging copies. These are covered by `test_smoke.py` and documented in `PERFORMANCE.md`.

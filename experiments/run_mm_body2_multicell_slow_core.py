"""MM-BODY-2 runner — regenerates results/mm_body2_multicell_slow_core pack.
Prefer re-running the in-repo history suite from prior session scripts if present.
This entrypoint documents the experiment id.
"""
from pathlib import Path
print("MM-BODY-2 pack expected at", Path("results/mm_body2_multicell_slow_core").resolve())
print("Re-run via project experiment harness if regenerating.")

"""Route all tests to a throwaway database.

Several test modules drop and recreate every table. Without this override
they would operate on the real harness.db and erase the agent's accumulated
learning (templates, mutations, harness versions, benchmarks) on every run.

This must happen before any ``siha`` import, because ``siha.db`` creates its
engine at import time.
"""

import os
import tempfile

_tmpdir = tempfile.mkdtemp(prefix="siha-test-db-")
os.environ.setdefault("SIHA_DB_PATH", os.path.join(_tmpdir, "test_harness.db"))

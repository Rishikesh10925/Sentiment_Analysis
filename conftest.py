import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Destructive database tests reload the dashboard tables. Point them at a
# throwaway database via TEST_DATABASE_URL so running the suite never wipes the
# demo corpus. Read-only API tests keep using the normal DATABASE_URL.
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

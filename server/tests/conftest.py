import os

# Tests never talk to a real BEN; they swap in fakes where needed.
os.environ.setdefault("BRIDGE_AI", "pass")

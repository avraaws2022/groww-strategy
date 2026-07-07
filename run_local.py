"""
Local runner - loads credentials from .env and runs the strategy.
Usage: python3 run_local.py

For Groww Cloud: copy strategy.py content and paste credentials directly.
"""
import os
import sys

# Load .env
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()
else:
    print("ERROR: .env file not found")
    sys.exit(1)

# Patch strategy.py credentials before importing
api_key = os.environ.get("GROWW_API_KEY", "")
secret = os.environ.get("GROWW_SECRET", "")

if not api_key or api_key == "your_api_key_here":
    print("ERROR: Set GROWW_API_KEY in .env")
    sys.exit(1)

if not secret or secret == "your_secret_here":
    print("ERROR: Set GROWW_SECRET in .env")
    sys.exit(1)

# Run strategy with env credentials
import time
from growwapi import GrowwAPI

# Override the strategy module credentials
import strategy
strategy.user_api_key = api_key
strategy.user_secret = secret

# Re-initialize with correct creds
print("Authenticating with Groww...")
access_token = GrowwAPI.get_access_token(api_key=api_key, secret=secret)
strategy.groww = GrowwAPI(access_token)
print("Authenticated. Running strategy...\n")

strategy.run()

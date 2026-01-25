#!/usr/bin/env python3
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from src.utils.nemo_manager import load_rails

def test_colang_syntax():
    print("🔍 Verifying Colang syntax in config/rails/...")
    try:
        # Attempt to load rails
        rails = load_rails()
        print("✅ Colang syntax is VALID.")
        return 0
    except Exception as e:
        print("\n❌ Colang syntax is INVALID.")
        print(f"Error details: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(test_colang_syntax())

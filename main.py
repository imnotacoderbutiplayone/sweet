import os
import sys

# Add the current directory to sys.path so Python can find local modules
sys.path.append(os.path.dirname(__file__))

# Debugging line to check contents of current directory
print("Current directory contents:", os.listdir())

# Try importing app_helpers
try:
    import app_helpers
    print("app_helpers imported successfully")
except ImportError as e:
    print(f"Error importing app_helpers: {e}")

# Create test file: /media/lewin/DATA1/fourthyear-project/API/test_ml.py
import sys
import os

# Add project to path
sys.path.insert(0, '/media/lewin/DATA1/fourthyear-project/API')

# Test imports
try:
    from API.ml.deposit_slip_recognizer import deposit_slip_recognizer
    print("✓ Deposit slip recognizer imported")
except Exception as e:
    print(f"✗ Import failed: {e}")

try:
    from API.ml.service import ml_service
    print("✓ ML service imported")
except Exception as e:
    print(f"✗ ML service import failed: {e}")

print("\nML Setup Complete!")
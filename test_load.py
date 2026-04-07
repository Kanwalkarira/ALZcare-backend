import sys

try:
    from app.main import app
    print("APP_LOAD_SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"APP_LOAD_ERROR: {e}")
    sys.exit(1)

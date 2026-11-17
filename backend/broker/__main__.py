"""`python -m backend.broker`: run the broker (the client starts it this way, from the plugin folder)."""
from .server import main

if __name__ == "__main__":
    raise SystemExit(main())

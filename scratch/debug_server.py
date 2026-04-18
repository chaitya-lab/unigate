"""Debug startup script for unigate."""
import traceback
from unigate.cli import main
import sys
import os

os.chdir(r"H:\2026\SelfAi\dev\chaitya\unigate")
sys.argv = ['unigate', 'start', '--config', 'test_routing.yaml', '--foreground']

try:
    print("Starting Unigate server...")
    print("Config: test_routing.yaml")
    print("URL: http://localhost:8080/unigate/")
    print("Web UI: http://localhost:8080/unigate/web/web")
    print()
    main()
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
    input("Press Enter to exit...")

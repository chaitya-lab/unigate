"""Quick startup script for unigate."""
from unigate.cli import main
import sys
import os

os.chdir(r"H:\2026\SelfAi\dev\chaitya\unigate")
sys.argv = ['unigate', 'start', '--config', 'test_routing.yaml', '--foreground']
print("Starting Unigate server...")
print("Press Ctrl+C to stop")
main()

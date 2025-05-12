"""
CLI Plugin for JunOS style route commands
Author: Drew Elliott
Email: drew.elliott@nokia.com
"""
from srlinux.mgmt.cli import CliPlugin, ExecuteError, KeyCompleter 
from srlinux.syntax import Syntax
import sys
import os

# Try potential base directories
potential_paths = [
    os.path.expanduser('~/cli'),
    '/etc/opt/srlinux/cli'
]

# Find the first valid path
import_base = None
for path in potential_paths:
    if os.path.exists(path):
        import_base = path
        break

if import_base is None:
    raise ImportError("Could not find a valid CLI plugin base directory")

# Construct the import path
import_path = os.path.join(import_base, "junos_route")


print(f"Import path: {import_path}")

# Add to Python path if not already present
if import_path not in sys.path:
    sys.path.insert(0, import_path)

from route_report import RouteReport

class Plugin(CliPlugin):
    """JunOS-style CLI plugin for route commands."""
    def load(self, cli, **_kwargs):
        print("Loading JunOS-style route plugin")
        # Create top-level route command
        route_cmd = cli.show_mode.add_command(
            Syntax('route'),
            callback=self._show_route
        )

    def _show_route(self, state, arguments, output, **_kwargs):
        if state.is_intermediate_command:
            return
        RouteReport()._show_routes(state, output, network_instance='default')
"""
CLI Plugin for JunOS style route commands
Author: Drew Elliott
Email: drew.elliott@nokia.com
"""
from srlinux.mgmt.cli import CliPlugin, ExecuteError, KeyCompleter 
from srlinux.syntax import Syntax
import sys
import os

class Plugin(CliPlugin):
    """JunOS-style CLI plugin."""
    def load(self, cli, **_kwargs):
        # Create top-level route command
        ip_cmd = cli.show_mode.add_command(
            Syntax('route'),
            callback=self._show_route
        )

    def _show_route(self, state, arguments, output, **_kwargs):
        print("state: %s" % state)
        print("Attributes and methods of state object:", dir(state))
        print("Attributes of state.yang_models object:", vars(state.yang_models))
        print("state.system_features:", state.system_features)
        print("state.root_node:", state.root_node)
        print("state.root_schema:", state.root_schema)
        print("state.cli_user_profile:", state.cli_user_profile)
        print("Attributes and methods of state.cli_user_profile:", dir(state.cli_user_profile))
        print("state.cli_user_profile.system_user:", state.cli_user_profile.system_user)
        print("checking state.is_intermediate_command: %s" % state.is_intermediate_command)
        print("\n_show_route called. \n\tstate.root_node:", state.root_node)
        print("\tstate.root_schema:", state.root_schema)

        return

"""

This script adds the the containing package as a valid debug adapter in the Debugger's settings

"""

from os.path import join, abspath, dirname, expanduser, exists
from Debugger.modules.debugger.debugger import Debugger
from threading import Timer
from shutil import copy
import sublime
import time
import sys
import os


adapter_type = "Nuke"  # NOTE: type name must be unique to each adapter
package_path = dirname(abspath(__file__))
adapter_path = join(package_path, "adapter")


# The version is only used for display in the GUI
version = "1.0"

# You can have several configurations here depending on your adapter's offered functionalities,
# but they all need a "label", "description", and "body"
config_snippets = [
    {
        "label": "Nuke: Python 2 Debugging",
        "description": "Run and Debug Python 2 code in Nuke",
        "body": {
            "name": "Nuke: Python 2 Debugging",  
            "type": adapter_type,
            "program": "\${file\}",
            "request": "attach",  # can only be attach or launch
            "interpreter": sys.executable,
            "debugpy":  # The host/port used to communicate with debugpy in Nuke
            {
                "host": "localhost",
                "port": 7004
            },
        }
    },
]

# The settings used by the Debugger to run the adapter.
settings = {
    "type": adapter_type,
    "command": [sys.executable, adapter_path]
}

# Instantiate variables needed for checking thread
running = False
check_speed = 3  # number of seconds to wait between checks for adapter presence in debugger instances

# Add server file to nuke if not present
user_nuke_path = join(expanduser("~"), ".nuke")
setup = join(adapter_path, 'resources', 'setup')

srv = join(user_nuke_path, "script_debug_server.py")
menu = join(user_nuke_path, "menu.py")

first_setup = False

if exists(join(user_nuke_path, 'debug_server.py')):
    os.remove(join(user_nuke_path, 'debug_server.py'))

if not exists(srv):
    copy(join(setup, 'script_debug_server.py'), srv)
    first_setup = True

if not exists(menu):
    with open(menu, 'w') as f:
        f.write('import script_debug_server')
else:
    with open(menu, 'r+') as f:
        contents = f.read()
        if "import script_debug_server" not in contents:
            f.write("\nimport script_debug_server")


def check_for_adapter():
    """
    Gets run in a thread to inject configuration snippets and version information 
    into adapter objects of type adapter_type in each debugger instance found
    """

    while running:

        for instance in Debugger.instances.values():
            adapter = getattr(instance, "adapters", {}).get(adapter_type, None)
            
            if adapter and not adapter.version:
                adapter.version = version
                adapter.snippets = config_snippets
        
        time.sleep(check_speed)


def plugin_loaded():
    """ Add adapter to debugger settings for it to be recognized """

    # Add entry to debugger settings
    debugger_settings = sublime.load_settings('debugger.sublime-settings')
    adapters_custom = debugger_settings.get('adapters_custom', {})

    adapters_custom[adapter_type] = settings

    debugger_settings.set('adapters_custom', adapters_custom)
    sublime.save_settings('debugger.sublime-settings')

    # Start checking thread
    global running
    running = True
    Timer(1, check_for_adapter).start()

    if first_setup:
        sublime.message_dialog(
            "Thanks for installing the Nuke debug adapter!\n"
            "Because this is your first time using the adapter, a one-time "
            "setup was performed. Please restart Nuke before continuing."
        )


def plugin_unloaded():
    """ This is done every unload just in case this adapter is being uninstalled """

    # Wait for checking thread to finish
    global running
    running = False
    time.sleep(check_speed + .1)

    # Remove entry from debugger settings
    debugger_settings = sublime.load_settings('debugger.sublime-settings')
    adapters_custom = debugger_settings.get('adapters_custom', {})

    adapters_custom.pop(adapter_type, "")

    debugger_settings.set('adapters_custom', adapters_custom)
    sublime.save_settings('debugger.sublime-settings')

    if exists(srv):
        os.remove(srv)

    if exists(menu):
        os.remove(menu)

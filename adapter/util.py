
from os.path import abspath, join, dirname, basename, split
from datetime import datetime
from threading import Thread
import json
import sys

# Import correct Queue
if (sys.version_info[0] == 3):
    from queue import Queue
else:  # Python 2
    from multiprocessing import Queue

#  Debugging this adapter
debug = True
log_file = abspath(join(dirname(__file__), 'log.txt'))

if debug:
    open(log_file, 'w+').close()  # Creates and/or clears the file

debugpy_path = join(abspath(dirname(__file__)), "python")


# --- Utility functions --- #

def log(msg, json_msg=None):
    if debug:

        if json_msg:
            msg += '\n' + json.dumps(json.loads(json_msg), indent=4)

        with open(log_file, 'a+') as f:
            f.write('\n' + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " - " + msg + '\n')


def run(func, args=()):
    Thread(target=func, args=args).start()


# --- Resources --- #

# Own constants
ATTACH_TEMPLATE = """
import sys
import os
debugpy_module = r"{debugpy_path}"
if debugpy_module not in sys.path:
    sys.path.insert(0, debugpy_module)

import debugpy

try:
    debugpy.configure(python="{interpreter}")
    debugpy.listen(("{hostname}",{port}))
except RuntimeError:
    x=1
finally:
    sys.stderr.write("\\n\\nConnection to Sublime Debugger is active.\\n\\n")
"""

# Used to run the module.
# Using stderr to print because printing
# to console doesn't work otherwise.
RUN_TEMPLATE = """
try:
    s = sys.stdout
    sys.stdout = sys.stderr

    current_directory = r"{dir}"
    if current_directory not in sys.path:
        sys.path.insert(0, current_directory)

    print('\\nDebugging {file_name}...\\n\\n')

    if '{file_name}' not in globals().keys():
        import {file_name}
    else:
        reload({file_name})

    print('\\n\\nDone.\\n')

    sys.stdout = s
    
except Exception as e:
    sys.stderr.write('Error while debugging: ' + str(e))
    raise e
"""

CONTENT_HEADER = "Content-Length: "

INITIALIZE_RESPONSE = """{
    "request_seq": 1,
    "body": {
        "supportsModulesRequest": true,
        "supportsConfigurationDoneRequest": true,
        "supportsDelayedStackTraceLoading": true,
        "supportsDebuggerProperties": true,
        "supportsEvaluateForHovers": true,
        "supportsSetExpression": true,
        "supportsGotoTargetsRequest": true,
        "supportsExceptionOptions": true,
        "exceptionBreakpointFilters": [
            {
                "filter": "raised",
                "default": false,
                "label": "Raised Exceptions"
            },
            {
                "filter": "uncaught",
                "default": true,
                "label": "Uncaught Exceptions"
            }
        ],
        "supportsCompletionsRequest": true,
        "supportsExceptionInfoRequest": true,
        "supportsLogPoints": true,
        "supportsValueFormattingOptions": true,
        "supportsHitConditionalBreakpoints": true,
        "supportsSetVariable": true,
        "supportTerminateDebuggee": true,
        "supportsConditionalBreakpoints": true
    },
    "seq": 1,
    "success": true,
    "command": "initialize",
    "message": "",
    "type": "response"
}"""

ATTACH_ARGS = """{{
    "name": "Nuke Python Debugger : Remote Attach",
    "type": "python",
    "request": "attach",
    "port": {port},
    "host": "{hostname}",
    "pathMappings": [
        {{
            "localRoot": "{dir}",
            "remoteRoot": "{dir}"
        }}
    ]
}}"""

PAUSE_REQUEST = """{{
    "command": "pause",
    "arguments": {{
        "threadId": 1
    }},
    "seq": {seq},
    "type": "request"
}}"""

NUKE_CMD_TEMPLATE = """
import traceback
import sys
import __main__

namespace = __main__.__dict__.get('_atom_plugin_SendToNuke')
if not namespace:
    namespace = __main__.__dict__.copy()
    __main__.__dict__['_atom_plugin_SendToNuke'] = namespace

namespace['__file__'] = r"{0}"
namespace['print'] = sys.stderr.write

try:
    execfile(r"{0}", namespace, namespace)
except:
    sys.stdout.write(traceback.format_exc())
    traceback.print_exc()
"""

# DISCONNECT_RESPONSE = """{{
#     "request_seq": {req_seq},
#     "body": {{}},
#     "seq": {seq},
#     "success": true,
#     "command": "disconnect",
#     "message": "",
#     "type": "response"
# }}"""


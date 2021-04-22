
"""

This script creates a connection between the Debugger and Foundry's Nuke for debugging Python 2.

"""

from util import (Queue, log, run, dirname, debugpy_path, join, split,
                  basename, ATTACH_TEMPLATE, ATTACH_ARGS, RUN_TEMPLATE, 
                  INITIALIZE_RESPONSE, NUKE_CMD_TEMPLATE, CONTENT_HEADER)
from interface import DebuggerInterface
from tempfile import gettempdir
import socket
import json

interface = None

processed_seqs = []
run_code = ""
attach_code = ""
last_seq = -1

debugpy_send_queue = Queue()
debugpy_socket = None


def main():
    """
    Initializes a python script through nuke, starts the thread to send information to debugger,
    then remains in a loop reading messages from debugger.
    """

    global interface

    # Create and start the interface with the debugger
    interface = DebuggerInterface(on_receive=on_receive_from_debugger)
    interface.start()


def on_receive_from_debugger(message):
    """
    Intercept the initialize and attach requests from the debugger
    while debugpy is being set up
    """

    global last_seq, avoiding_continue_stall

    # Load message contents into a dictionary
    contents = json.loads(message)
    last_seq = contents.get('seq')

    log('Received from Debugger:', message)

    # Get the type of command the debugger sent
    cmd = contents['command']
    
    if cmd == 'initialize':
        # Run init request once nuke connection is established and send success response to the debugger
        interface.send(json.dumps(json.loads(INITIALIZE_RESPONSE)))  # load and dump to remove indents
        processed_seqs.append(contents['seq'])
    
    elif cmd == 'attach':
        # time to attach to nuke
        run(attach_to_nuke, (contents,))

        # Change arguments to valid ones for debugpy
        config = contents['arguments']
        new_args = ATTACH_ARGS.format(
            dir=dirname(config['program']).replace('\\', '\\\\'),
            hostname=config['debugpy']['host'],
            port=int(config['debugpy']['port']),
            # filepath=config['program'].replace('\\', '\\\\')
        )

        # Update the message with the new arguments to then be sent to debugpy
        contents = contents.copy()
        contents['arguments'] = json.loads(new_args)
        message = json.dumps(contents)  # update contents to reflect new args

        log("New attach arguments loaded:", new_args)
    
    elif cmd == 'continue':
        avoiding_continue_stall = True

    # Then just put the message in the debugpy queue
    debugpy_send_queue.put(message)


def attach_to_nuke(contents):
    """
    Defines commands to send to Nuke, and sends the attach code to it.
    """

    global run_code, attach_code, nuke_path
    config = contents['arguments']

    # Format the simulated attach response to send it back to the debugger
    # while we set up the debugpy in the background
    attach_code = ATTACH_TEMPLATE.format(
        debugpy_path=debugpy_path,
        hostname=config['debugpy']['host'],
        port=int(config['debugpy']['port']),
        interpreter=config['interpreter'],
    )

    # Copy code to temporary file and start a Nuke console with it
    try: 
        send_code_to_nuke(attach_code)
    except Exception as e:
        # Raising exceptions shows the text in the Debugger's output.
        # Raise an error to show a potential solution to this problem.
        log("Exception occurred: \n\n" + str(e))
        raise Exception(
            """
            
            
            
                        Could not connect to Nuke.

                Please ensure Nuke is running. If this is your first time
                using the debug adapter, try restarting Nuke.
            """
        )

    run_code = RUN_TEMPLATE.format(
        hostname=config['debugpy']['host'],
        port=int(config['debugpy']['port']),
        dir=dirname(config['program']),
        file_name=split(config['program'])[1][:-3] or basename(split(config['program'])[0])[:-3]
    )

    # Then start the Nuke debugging threads
    run(start_debugging, ((config['debugpy']['host'], int(config['debugpy']['port'])),))


def send_code_to_nuke(code):
    """
    Copies code to temporary file, formats execution template code with file location, 
    and sends execution code to Nuke via socket connection.

    Inspired by send_to_nuke.py at https://github.com/tokejepsen/atom-foundry-nuke
    """

    # Create a temporary file, keeping its path, and
    # populate it with the given code to run
    filepath = join(gettempdir(), 'temp.py')
    with open(filepath, "w") as file:
        file.write(code)

    # throws error if it fails
    log("Sending code to Nuke...")

    # Format the code wrapper with the file's path
    # This wrapper allows the code to execute in its own namespace
    cmd = NUKE_CMD_TEMPLATE.format(filepath)

    ADDR = ("localhost", 8888)

    # Create a socket and connect to server in Nuke
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(ADDR)

    # Send the formatted template to the server
    client.send(cmd.encode("UTF-8"))
    client.close()
    
    log("Success")


def start_debugging(address):
    """
    Connects to debugpy in Nuke, then starts the threads needed to
    send and receive information from it
    """

    log("Connecting to " + address[0] + ":" + str(address[1]))

    # Create the socket used to communicate with debugpy
    global debugpy_socket
    debugpy_socket = socket.create_connection(address)

    log("Successfully connected to Nuke for debugging. Starting...")

    # Start a thread that sends requests to debugpy
    run(debugpy_send_loop)

    fstream = debugpy_socket.makefile()

    while True:
        try:
            # Wait for the CONTENT_HEADER to show up,
            # then get the length of the content following it
            content_length = 0
            while True:
                header = fstream.readline()
                if header:
                    header = header.strip()
                if not header:
                    break
                if header.startswith(CONTENT_HEADER):
                    content_length = int(header[len(CONTENT_HEADER):])

            # Read the content of the response, then call the callback
            if content_length > 0:
                total_content = ""
                while content_length > 0:
                    content = fstream.read(content_length)
                    content_length -= len(content)
                    total_content += content

                if content_length == 0:
                    message = total_content
                    on_receive_from_debugpy(message)

        except Exception as e:
            # Problem with socket. Close it then return

            log("Failure reading Nuke's debugpy output: \n" + str(e))
            debugpy_socket.close()
            break


def debugpy_send_loop():
    """
    The loop that waits for items to show in the send queue and prints them.
    Blocks until an item is present
    """

    while True:
        # Get the first message off the queue
        msg = debugpy_send_queue.get()
        if msg is None:
            # get() is blocking, so None means it was intentionally
            # added to the queue to stop this loop, or that a problem occurred
            return
        else:
            try:
                # First send the content header with the length of the message, then send the message
                debugpy_socket.send(bytes(CONTENT_HEADER + '{}\r\n\r\n'.format(len(msg)), 'UTF-8'))
                debugpy_socket.send(msg.encode('UTF-8'))
                log('Sent to debugpy:', msg)
            except OSError:
                log("Debug socket closed.")
                return
            except Exception as e:
                log("Error sending to debugpy: " + str(e))
                return


def on_receive_from_debugpy(message):
    """
    Handles messages going from debugpy to the debugger
    """

    global inv_seq, artificial_seqs, waiting_for_pause_event, avoiding_continue_stall, stashed_event

    # Load the message into a dictionary
    c = json.loads(message)
    seq = int(c.get('request_seq', -1))  # a negative seq will never occur
    cmd = c.get('command', '')

    if cmd == 'configurationDone':
        # When Debugger & debugpy are done setting up, send the code to debug
        log('Received from debugpy:', message)
        interface.send(message)
        send_code_to_nuke(run_code)
        return

    # Send responses and events to debugger
    if seq in processed_seqs:
        # Should only be the initialization request
        log("Already processed, debugpy response is:", message)
    else:
        # Send the message normally to the debugger
        log('Received from debugpy:', message)
        interface.send(message)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(str(e))
        raise e

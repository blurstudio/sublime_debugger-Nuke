
"""

This script creates a connection between the Debugger and Foundry's Nuke for debugging Python 2.

"""

from util import (Queue, log, run, dirname, ptvsd_path, join, split,
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

ptvsd_send_queue = Queue()
ptvsd_socket = None


def main():
    """
    Initializes a python script through nuke, starts the thread to send information to debugger,
    then remains in a loop reading messages from debugger.
    """

    global interface

    interface = DebuggerInterface(on_receive=on_receive_from_debugger)
    interface.start()


def on_receive_from_debugger(message):
    """
    Intercept the initialize and attach requests from the debugger
    while ptvsd is being set up
    """

    global last_seq, avoiding_continue_stall

    contents = json.loads(message)
    last_seq = contents.get('seq')

    log('Received from Debugger:', message)

    cmd = contents['command']
    
    if cmd == 'initialize':
        # Run init request once nuke connection is established and send success response to the debugger
        interface.send(json.dumps(json.loads(INITIALIZE_RESPONSE)))  # load and dump to remove indents
        processed_seqs.append(contents['seq'])
        return
    
    elif cmd == 'attach':
        # time to attach to nuke
        run(attach_to_nuke, (contents,))

        # Change arguments to valid ones for ptvsd
        config = contents['arguments']
        new_args = ATTACH_ARGS.format(
            dir=dirname(config['program']).replace('\\', '\\\\'),
            hostname=config['ptvsd']['host'],
            port=int(config['ptvsd']['port']),
            # filepath=config['program'].replace('\\', '\\\\')
        )

        contents = contents.copy()
        contents['arguments'] = json.loads(new_args)
        message = json.dumps(contents)  # update contents to reflect new args

        log("New attach arguments loaded:", new_args)
    
    elif cmd == 'continue':
        avoiding_continue_stall = True

    # Then just put the message in the ptvsd queue
    ptvsd_send_queue.put(message)


def attach_to_nuke(contents):
    """
    Defines commands to send to Nuke, and sends the attach code to it.
    """

    global run_code, attach_code, nuke_path
    config = contents['arguments']

    # format attach code appropriately
    attach_code = ATTACH_TEMPLATE.format(
        ptvsd_path=ptvsd_path,
        hostname=config['ptvsd']['host'],
        port=int(config['ptvsd']['port'])
    )

    # Copy code to temporary file and start a Nuke console with it
    try: 
        send_code_to_nuke(attach_code)
    except Exception as e:
        log("Exception occurred: \n\n" + str(e))
        raise Exception(
            """
            
            
            
                        Could not connect to Nuke.

                Please ensure Nuke is running. If this is your first time
                using the debug adapter, try restarting Nuke.
            """
        ).with_traceback()

    run_code = RUN_TEMPLATE.format(
        hostname=config['ptvsd']['host'],
        port=int(config['ptvsd']['port']),
        dir=dirname(config['program']),
        file_name=split(config['program'])[1][:-3] or basename(split(config['program'])[0])[:-3]
    )

    # Then start the Nuke debugging threads
    run(start_debugging, ((config['ptvsd']['host'], int(config['ptvsd']['port'])),))


def send_code_to_nuke(code):
    """
    Copies code to temporary file, formats execution template code with file location, 
    and sends execution code to Nuke via socket connection.

    Inspired by send_to_nuke.py at https://github.com/tokejepsen/atom-foundry-nuke
    """

    filepath = join(gettempdir(), 'temp.py')
    with open(filepath, "w") as file:
        file.write(code)

    # throws error if it fails
    log("Sending code to Nuke...")

    cmd = NUKE_CMD_TEMPLATE.format(filepath)

    ADDR = ("localhost", 8888)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(ADDR)

    client.send(cmd.encode("UTF-8"))
    client.close()
    
    log("Success")


def start_debugging(address):
    """
    Connects to ptvsd in Nuke, then starts the threads needed to
    send and receive information from it
    """

    log("Connecting to " + address[0] + ":" + str(address[1]))

    global ptvsd_socket
    ptvsd_socket = socket.create_connection(address)

    log("Successfully connected to Nuke for debugging. Starting...")

    run(ptvsd_send_loop)  # Start sending requests to ptvsd

    fstream = ptvsd_socket.makefile()

    while True:
        try:
            content_length = 0
            while True:
                header = fstream.readline()
                if header:
                    header = header.strip()
                if not header:
                    break
                if header.startswith(CONTENT_HEADER):
                    content_length = int(header[len(CONTENT_HEADER):])

            if content_length > 0:
                total_content = ""
                while content_length > 0:
                    content = fstream.read(content_length)
                    content_length -= len(content)
                    total_content += content

                if content_length == 0:
                    message = total_content
                    on_receive_from_ptvsd(message)

        except Exception as e:
            log("Failure reading Nuke's ptvsd output: \n" + str(e))
            ptvsd_socket.close()
            break


def ptvsd_send_loop():
    """
    The loop that waits for items to show in the send queue and prints them.
    Blocks until an item is present
    """

    while True:
        msg = ptvsd_send_queue.get()
        if msg is None:
            return
        else:
            try:
                ptvsd_socket.send(bytes('Content-Length: {}\r\n\r\n'.format(len(msg)), 'UTF-8'))
                ptvsd_socket.send(bytes(msg, 'UTF-8'))
                log('Sent to ptvsd:', msg)
            except OSError:
                log("Debug socket closed.")
                return


def on_receive_from_ptvsd(message):
    """
    Handles messages going from ptvsd to the debugger
    """

    global inv_seq, artificial_seqs, waiting_for_pause_event, avoiding_continue_stall, stashed_event

    c = json.loads(message)
    seq = int(c.get('request_seq', -1))  # a negative seq will never occur
    cmd = c.get('command', '')

    if cmd == 'configurationDone':
        # When Debugger & ptvsd are done setting up, send the code to debug
        log('Received from ptvsd:', message)
        interface.send(message)
        send_code_to_nuke(run_code)
        return
    
    elif cmd == "variables":
        # Hide the __builtins__ variable (causes errors in the debugger gui)
        vars = c['body'].get('variables')
        if vars:
            toremove = []
            for var in vars:
                if var['name'] in ('__builtins__', '__doc__', '__file__', '__name__', '__package__'):
                    toremove.append(var)
            for var in toremove:
                vars.remove(var)
            message = json.dumps(c)

    # Send responses and events to debugger
    if seq in processed_seqs:
        # Should only be the initialization request
        log("Already processed, ptvsd response is:", message)
    else:
        log('Received from ptvsd:', message)
        interface.send(message)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(str(e))
        raise e

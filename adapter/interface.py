
from sys import stdin, stdout
from util import CONTENT_HEADER, run, log, Queue


class DebuggerInterface:
    """
    Provides a simple interface to capture and send 
    messages from/to the debugger vis stdin/stdout.
    """

    def __init__(self, on_receive = None):
        self.send_queue = Queue()
        self.running = False
        self.callback = on_receive

    def start(self):
        if not self.running:
            self.running = True
            run(self._debugger_send_loop)
            self._read_debugger_input()
    
    def start_nonblocking(self):
        if not self.running:
            self.running = True
            run(self._debugger_send_loop)
            run(self._read_debugger_input)

    def stop(self):
        if self.running:
            self.running = False

    def send(self, message):
        self.send_queue.put(message)

    def _read_debugger_input(self):
        """
        Reads DAP messages sent from the debugger through stdin and calls the
        function passed in as the callback with the message recieved.
        """

        while self.running:
            try:
                content_length = 0
                while self.running:
                    header = stdin.readline()
                    if header:
                        header = header.strip()
                    if not header:
                        break
                    if header.startswith(CONTENT_HEADER):
                        content_length = int(header[len(CONTENT_HEADER):])

                if content_length > 0:
                    total_content = ""
                    while content_length > 0:
                        content = stdin.read(content_length)
                        content_length -= len(content)
                        total_content += content

                    if content_length == 0:
                        message = total_content
                        if self.callback:
                            self.callback(message)

            except Exception as e:
                log("Failure reading stdin: " + str(e))
                log(header)
                log(message)
                log(total_content)
                raise e


    def _debugger_send_loop(self):
        """
        Waits for items to show in the send queue and prints them.
        Blocks until an item is present
        """

        while self.running:
            msg = self.send_queue.get()
            if msg is None:
                return
            else:
                try:
                    stdout.write('Content-Length: {}\r\n\r\n'.format(len(msg)))
                    stdout.write(msg)
                    stdout.flush()
                    log('Sent to Debugger:', msg)
                except Exception as e:
                    log("Failure writing to stdout (normal on exit):" + str(e))


'''
    Simple socket server using threads
'''

import socket
import threading

import nuke


HOST = ''
PORT = 8888


def _exec(command):
    exec(command)


def server_start():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen(5)

    while True:
        client, _ = s.accept()
        try:
            command = client.recv(4096)
            if command:
                nuke.executeInMainThread(_exec, args=(command))
        except SystemExit:
            result = self.encode('SERVER: Shutting down...')
            if result:
                client.send(result)
            raise
        finally:
            client.close()


t = threading.Thread(None, server_start)
t.setDaemon(True)
t.start()

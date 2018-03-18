import json
import SocketServer
import socket
import logging
import threading

__author__ = 'Wolfrax'

"""
This implements server functionality for spots, enabling clients to access spots data over network.

The Spots server implements a threaded server, one thread per request. The requests follow a simple protocol
    "GET DATA STR": message from the client will return the radar blip messages in serialized/json format
    "GET STATISTICS STR": message from the client will return spots statistics in serialized/json format
    "GET FLIGHT_DB STR": message from the client will return spots flight database in serialized/json format
"""


class TCPRequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        cmd = self.request.recv(1024)

        if cmd == "GET DATA STR":
            response = self.server.radar.get_blips_serialized()
        elif cmd == "GET STATISTICS STR":
            response = self.server.radar.get_statistics()
        elif cmd == "GET FLIGHT_DB STR":
            response = self.server.radar.get_flight_db()
        else:
            return

        self.request.sendall(json.dumps(response))


class SpotsServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    """
    A threaded TCP server handling requests through the TCPRequestHandler.
    It will start a new thread for each request, these are managed by the method handle
    """
    def __init__(self, server_address, radar_object):
        SocketServer.TCPServer.allow_reuse_address = True

        SocketServer.TCPServer.__init__(self, server_address, TCPRequestHandler)

        # reuse a local socket in TIME_WAIT state (SO_REUSEADDR)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.server_thread = threading.Thread(target=self.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.name = "Socket server"

        self.radar = radar_object
        self.logger = logging.getLogger('spots.Server')
        self.logger.info("Message server initialized")

    def start(self):
        self.server_thread.start()

    def die(self):
        self.shutdown()
        self.server_close()

#!/usr/bin/env python

from flask import Flask
import socket


__author__ = 'Wolfrax'

app = Flask(__name__)
cfg_server_address = 'localhost'
cfg_server_port = 5051


def get_msg(message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((cfg_server_address, cfg_server_port))
    data = []
    try:
        sock.sendall(message)
        while True:
            stream = sock.recv(1024)
            if not stream:
                break
            else:
                data.append(stream)
        data = ''.join(data)
    finally:
        sock.close()
        return data


@app.route("/spots/data")
def spots_data():
    return app.response_class(get_msg("GET DATA STR"), content_type='application/json')


@app.route("/spots/statistics")
def spots_statistics():
    return app.response_class(get_msg("GET STATISTICS STR"), content_type='application/json')


if __name__ == "__main__":
    print "Will listen on {}:{}".format(cfg_server_address, cfg_server_port)
    app.run(host='0.0.0.0', debug=True)

#!/usr/bin/env python

from flask import Flask
import socket
import datetime


__author__ = 'Wolfrax'

app = Flask(__name__)
cfg_server_address = 'localhost'
cfg_server_port = 5051


def get_msg(message):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    except socket.error as msg:
        print "{} Sock err (1): {}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
        sock = None
        return None

    try:
        sock.connect((cfg_server_address, cfg_server_port))
    except socket.error as msg:
        print "{} Sock err (2): {}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
        sock = None
        return None

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
    except socket.error as msg:
        print "{} Sock err (3): {}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    finally:
        sock.close()
        return data


@app.route("/spots/data")
def spots_data():
    return app.response_class(get_msg("GET DATA STR"), content_type='application/json')


@app.route("/spots/statistics")
def spots_statistics():
    return app.response_class(get_msg("GET STATISTICS STR"), content_type='application/json')


@app.route("/spots/flight_db")
def spots_flight_db():
    return app.response_class(get_msg("GET FLIGHT_DB STR"), content_type='application/json')


if __name__ == "__main__":
    print "Will listen on {}:{}".format(cfg_server_address, cfg_server_port)
    app.run(host='0.0.0.0', debug=True)

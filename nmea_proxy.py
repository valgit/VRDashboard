# coding: utf-8 

import http.server
import socketserver
import socket
import argparse
import logging
import threading

parser = argparse.ArgumentParser()

parser.add_argument(
    '--bind',
    help='Set the server interface to bind (default 0.0.0.0)')

parser.add_argument(
    '--outport',
    help='Set outbound port base (default 10000)')

parser.add_argument(
    '--port',
    help='Set the HTTP port to bind (default 8081)')

args = parser.parse_args()
HOST = (args.bind if args.bind else '0.0.0.0')
OUTPORT = (int(args.outport) if args.outport else 10000)
PORT = (int(args.port) if args.port else 8081)


connections = dict()
sockets = dict()


class NMEAHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(s):
        content_len = int(s.headers.get('Content-Length'))
        post_body = s.rfile.read(content_len)
        race_id = s.path[6:9]
        forward_message(int(race_id), post_body)
        s.send_response(204)
        s.send_header('Access-Control-Allow-Origin', '*')
        s.end_headers()

    def log_message(self, format, *args):        
        pass


def forward_message(conn_id, message):
    conn = find_or_create_connection(conn_id)
    # should loop on all conn
    if conn:
        try:
            conn.send(message + '\r\n'.encode('ascii'))
        except Exception:
            logging.info('Connection lost on port ' + str(conn_id)
                         + ', closing.')
            conn.close()
            connections.pop(conn_id, None)


def find_or_create_connection(conn_id):
    # open the server connection if needed
    if conn_id not in sockets:            
        newthread = AcceptThread(conn_id)
        newthread.start()

    if conn_id in connections:
        return connections[conn_id]
    else:
        conn = None                
        return conn


def create_socket(conn_id):
    logging.info('Creating NMEA socket for race ID ' + str(conn_id))
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(False)
    try:
        sock.bind((HOST, OUTPORT + conn_id))
    except socket.error as e:
        logging.info(str(e))

    sock.listen(5)
    return sock


# acceptthread

class AcceptThread(threading.Thread):
    def __init__(self,conn_id):
        super().__init__()
        self.conn_id = conn_id
        sockets[conn_id] = create_socket(conn_id)

    def run(self): 
        logging.debug('running with conn %s', self.conn_id)
        while True:  
            conn = accept_connection(sockets[self.conn_id])
            logging.debug('got conn %s', self.conn_id)
        #    add conn to table
            if conn:
                connections[self.conn_id] = conn
    
    

def accept_connection(sock):
    try:
        (conn, address) = sock.accept()
        logging.info('Accepted connection on port '
                     + str(sock.getsockname()[1]))
        return conn
    except IOError:
        return None



logging.basicConfig(level=logging.DEBUG)

logging.info("Creating httpd Server")
server = socketserver.TCPServer(("", PORT), NMEAHandler)
logging.info("httpd listening on port " + str(PORT))

try:
    server.serve_forever()
except KeyboardInterrupt:
    pass

finally:
    logging.info('Cleaning up')
    server.server_close()
    logging.info('Stopping httpd\n')

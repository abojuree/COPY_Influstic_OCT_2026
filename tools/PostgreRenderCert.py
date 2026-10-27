#!/usr/bin/env python

import argparse
import socket
import ssl
import struct
import base64
import os
from icecream import ic

# postgresql://admin:@dpg-co9u07a0si5c739j3bh0-a.oregon-postgres.render.com/socialscannerdb
# PostgreRenderCert.py oregon-postgres.render.com > server.crt

try:
    from urlparse import urlparse
except ImportError:
    from urllib.parse import urlparse


def main(args):
    # args = get_args()
    target = get_target_address_from_args(args)
    sock = socket.create_connection(target)
    try:
        certificate_as_pem = get_certificate_from_socket(sock)
        return certificate_as_pem.decode('utf-8')
    except Exception as exc:
        return 'Something failed while fetching certificate: {0}\n'.format(exc)
    finally:
        sock.close()


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('database', help='Either an IP address, hostname or URL with host and port')
    return parser.parse_args()


def get_target_address_from_args(args):
    specified_target = args.database
    if '//' not in specified_target:
        specified_target = '//' + specified_target
    parsed = urlparse(specified_target)
    return (parsed.hostname, parsed.port or 5433)


def get_certificate_from_socket(sock):
    request_ssl(sock)
    ssl_context = get_ssl_context()
    sock = ssl_context.wrap_socket(sock)
    sock.do_handshake()
    certificate_as_der = sock.getpeercert(binary_form=True)
    certificate_as_pem = encode_der_as_pem(certificate_as_der)
    return certificate_as_pem


def request_ssl(sock):
    # 1234.5679 is the magic protocol version used to request TLS, defined
    # in pgcomm.h)
    version_ssl = postgres_protocol_version_to_binary(1234, 5679)
    length = struct.pack('!I', 8)
    packet = length + version_ssl

    sock.sendall(packet)
    data = read_n_bytes_from_socket(sock, 1)
    if data != b'S':
        raise Exception('Backend does not support TLS')


def get_ssl_context():
    # Return the strongest SSL context available locally
    for proto in ('PROTOCOL_TLSv1_2', 'PROTOCOL_TLSv1', 'PROTOCOL_SSLv23'):
        protocol = getattr(ssl, proto, None)
        if protocol:
            break
    return ssl.SSLContext(protocol)


def encode_der_as_pem(cert):
    # Convert DER to PEM format
    b64_cert = base64.b64encode(cert).decode('ascii')
    
    # Split into 64-character lines
    lines = [b64_cert[i:i+64] for i in range(0, len(b64_cert), 64)]
    
    # Add PEM headers and format
    pem = ['-----BEGIN CERTIFICATE-----']
    pem.extend(lines)
    pem.append('-----END CERTIFICATE-----')
    
    return '\n'.join(pem).encode('ascii')


def read_n_bytes_from_socket(sock, n):
    buf = bytearray(n)
    view = memoryview(buf)
    while n:
        nbytes = sock.recv_into(view, n)
        view = view[nbytes:] # slicing views is cheap
        n -= nbytes
    return buf


def postgres_protocol_version_to_binary(major, minor):
    return struct.pack('!I', major << 16 | minor)


def generate_certificate():
    # Fixed hostname
    hostname = "oregon-postgres.render.com"
    # Create an ArgParser namespace with the hostname
    args = argparse.Namespace(database=hostname)
    
    # Get the certificate
    cert = main(args)
    
    # Define the output file path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    cert_path = os.path.join(current_dir, 'server.crt')
    
    # Save the certificate to file
    with open(cert_path, 'w') as f:
        f.write(cert)
    
    return cert_path

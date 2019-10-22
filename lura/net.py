import ipaddress
import socket

def resolve(hostname):
  try:
    info = socket.getaddrinfo(hostname, 80, proto=socket.IPPROTO_TCP)
    return info[0][4][0]
  except socket.gaierror:
    return None

def is_ip_address(string):
  try:
    ipaddress.ip_address(string)
    return True
  except ValueError:
    return False

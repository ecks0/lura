import socket

def address(hostname):
  try:
    info = socket.getaddrinfo(hostname, 80, proto=socket.IPPROTO_TCP)
    return info[0][4][0]
  except socket.gaierror:
    return None

import io
import ipaddress
import requests
import socket
import sys

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

def wgetfd(url, fd, bufsize=64*1024):
  with requests.get(url, stream=True) as req:
    req.raise_for_status()
    for buf in req.iter_content(chunk_size=bufsize):
      if buf:
        fd.write(buf)

def wgetf(url, path, bufsize=64*1024):
  with open(path, 'wb') as pathf:
    self.wgetfd(url, pathf, bufsize)

def wget(url):
  with io.BytesIO() as buf:
    wgetfd(url, buf)
    return buf.getvalue()

def wgets(url, encoding=None):
  encoding = encoding or sys.getdefaultencoding()
  return wget(url).decode(encoding)

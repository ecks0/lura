'SSL RPC services using RPyC.'

import rpyc
from lura import logs
from rpyc.core.service import SlaveService
from rpyc.utils.authenticators import SSLAuthenticator
from rpyc.utils.server import ThreadedServer

log = logs.get_logger(__name__)

Service = SlaveService

def listen(
  service, host, port, key_path, cert_path, sync_timeout, backlog, log=log
):
  name = service.get_service_name()
  log.info(f'Service listening: {name}@{host}:{port}')
  protocol_config = dict(
    allow_all_attrs = True,
    allow_delattr = True,
    allow_public_attrs = True,
    allow_setattr = True,
    logger = log,
    sync_request_timeout = sync_timeout)
  authenticator = SSLAuthenticator(key_path, cert_path)
  server = ThreadedServer(service,
    hostname=host, port=port, protocol_config=protocol_config,
    authenticator=authenticator, backlog=backlog, logger=log)
  server.start()

def patch_close(conn, name):
  conn_close = conn.close
  def close(*args, **kwargs):
    log.info(f'Disconnecting from service: {name}@{conn.host}:{conn.port}')
    conn_close(*args, **kwargs)
    conn.close = conn_close
  conn.close = close

def connect(host, port, key_path, cert_path, sync_timeout, log=log):
  log.info(f'Connecting to service: {host}:{port}')
  protocol_config = dict(
    allow_all_attrs = True,
    allow_delattr = True,
    allow_public_attrs = True,
    allow_setattr = True,
    logger = log,
    sync_request_timeout = sync_timeout)
  conn = rpyc.ssl_connect(
    host, port=port, keyfile=key_path, certfile=cert_path,
    config=protocol_config)
  name = conn.root.get_service_name()
  patch_close(conn, name)
  conn.host = host
  conn.port = port
  conn.service = conn.root
  log.info(f'Connected to service: {name}@{host}:{port}')
  return conn

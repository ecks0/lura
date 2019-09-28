'SSL RPC services using RPyC.'

import rpyc
from lura import logs
from rpyc.core.service import SlaveService
from rpyc.utils.authenticators import SSLAuthenticator
from rpyc.utils.server import ThreadedServer

logger = logs.get_logger(__name__)

Service = SlaveService

def listen(service, host, port, key_path, cert_path, sync_timeout, backlog):

  log = logger[listen.log_level]
  name = service.get_service_name()
  log(f'[{name}@{host}:{port}] Listening')
  protocol_config = dict(
    allow_all_attrs = True,
    allow_delattr = True,
    allow_public_attrs = True,
    allow_setattr = True,
    logger = logger,
    sync_request_timeout = sync_timeout)
  authenticator = SSLAuthenticator(key_path, cert_path)
  server = ThreadedServer(service,
    hostname=host, port=port, protocol_config=protocol_config,
    authenticator=authenticator, backlog=backlog, logger=logger)
  server.start()

listen.log_level = logger.INFO

def _patch_close(conn, name, log):
  conn_close = conn.close
  def close(*args, **kwargs):
    log(f'[{name}@{conn.host}:{conn.port}] Disconnected')
    conn_close(*args, **kwargs)
    conn.close = conn_close
  conn.close = close

def connect(host, port, key_path, cert_path, sync_timeout):
  log = logger[connect.log_level]
  log(f'[{host}:{port}] Connecting to service')
  protocol_config = dict(
    allow_all_attrs = True,
    allow_delattr = True,
    allow_public_attrs = True,
    allow_setattr = True,
    logger = logger,
    sync_request_timeout = sync_timeout)
  conn = rpyc.ssl_connect(
    host, port=port, keyfile=key_path, certfile=cert_path,
    config=protocol_config)
  name = conn.root.get_service_name()
  _patch_close(conn, name, log)
  conn.host = host
  conn.port = port
  conn.service = conn.root
  log(f'[{name}@{conn.host}:{conn.port}] Connected')
  return conn

connect.log_level = logger.INFO

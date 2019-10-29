'SSL RPC services using RPyC.'

import logging
import rpyc
from rpyc.core.service import SlaveService
from rpyc.utils.authenticators import SSLAuthenticator
from rpyc.utils.server import ThreadedServer

logger = logging.getLogger(__name__)

Service = SlaveService

def listen(service, host, port, key_path, cert_path, sync_timeout, backlog):

  name = service.get_service_name()
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

def _patch_close(conn, on_close):
  conn_close = conn.close
  def close(*args, **kwargs):
    on_close()
    conn_close(*args, **kwargs)
    conn.close = conn_close
  conn.close = close

def connect(
  host, port, key_path, cert_path, sync_timeout, on_connect=None,
  on_close=None
):
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
  if on_connect:
    on_connect()
  name = conn.root.get_service_name()
  if on_close:
    _patch_close(conn, on_close)
  conn.host = host
  conn.port = port
  conn.service = conn.root
  return conn

'Remote procedure calls using rpyc.'

import logging
import rpyc
from rpyc.core.protocol import Connection
from rpyc.core.service import SlaveService
from rpyc.utils.authenticators import SSLAuthenticator
from rpyc.utils.server import ThreadedServer
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

class Service(SlaveService):
  'Base service class.'
  
  pass

def listen(
  service: Service,
  host: str,
  port: int,
  key_path: str,
  cert_path: str,
  sync_timeout: int,
  backlog: int
) -> None:
  'Listen for incoming RPC client connections.'

  name = service.get_service_name()
  protocol_config = dict(
    allow_all_attrs = True,
    allow_delattr = True,
    allow_public_attrs = True,
    allow_setattr = True,
    logger = logger,
    sync_request_timeout = sync_timeout
  )
  authenticator = SSLAuthenticator(key_path, cert_path)
  server = ThreadedServer(service,
    hostname=host, port=port, protocol_config=protocol_config,
    authenticator=authenticator, backlog=backlog, logger=logger)
  server.start()

def _patch_close(conn: Connection, on_close: Callable[[], Any]) -> None:
  'Patch a connection object to call `on_close` when the connection is closed.'

  orig_close = conn.close
  def patched_close(*args, **kwargs):
    on_close()
    orig_close(*args, **kwargs)
    conn.close = orig_close
  conn.close = patched_close

def connect(
  host: str,
  port: int,
  key_path: str,
  cert_path: str,
  sync_timeout: int,
  on_connect: Optional[Callable[[], Any]] = None,
  on_close: Optional[Callable[[], Any]] = None,
) -> Connection:
  'Connect to an RPC service.'

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

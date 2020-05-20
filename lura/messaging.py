'Send messages to messaging services, e.g. Teams or Discord.'

import json
import logging
import queue
import requests
from lura.attrs import attr
from lura.utils import format_exc_info
from lura.threads import Thread
from time import sleep
from typing import Any, Mapping, Optional, Sequence
from typing_extensions import Protocol

logger = logging.getLogger(__name__)

class Message:

  title: Optional[str]
  subtitle: Optional[str]
  summary: Optional[str]
  fields: Optional[Mapping[str, str]]

  def __init__(
    self,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    summary: Optional[str] = None,
    fields: Optional[Mapping[str, str]] = None,
  ) -> None:
  
    super().__init__()
    self.title = title
    self.subtitle = subtitle
    self.summary = summary
    self.fields = fields

class Service(Protocol):

  def __init__(
    self,
    webhook: str,
    timeout: float,
    **kwargs: Any
  ) -> None:

    ...

  def send(
    self,
    message: Message,
    **kwargs: Any
  ) -> None:

    ...

class Teams:
  'Send messages to Microsoft Teams.'

  _webhook: str
  _timeout: float

  def __init__(
    self,
    webhook: str,
    timeout: float = 20.0,
    **kwargs: Any
  ) -> None:

    super().__init__()
    self._webhook = webhook
    self._timeout = timeout

  def send(
    self,
    message: Message,
    **kwargs: Any
  ) -> None:
    'Send messages to Microsoft Teams.'

    payload = {
      '@type': 'MessageCard',
      '@context': 'http://schema.org/extensions',
      'summary': message.summary or '', # XXX what does this actually do?
      'sections': [
        {
          'activityTitle': message.title or '',
          'activitySubtitle': message.subtitle or '',
          'facts': [
            {'name': n, 'value': v} for (n, v) in (message.fields or {}).items()
          ],
        }]}
    res = requests.post(
      self._webhook,
      headers = {'Content-Type': 'application/json'},
      data = json.dumps(payload),
      timeout = self._timeout
    )
    res.raise_for_status()

class Discord:
  'Send messages to Discord.'

  _webhook: str
  _timeout: float

  def __init__(
    self,
    webhook: str,
    timeout: float = 20.0,
    **kwargs: Any
  ) -> None:

    super().__init__()
    self._webhook = webhook
    self._timeout = timeout

  def send(
    self,
    message: Message,
    **kwargs: Any
  ) -> None:
    'Send messages to Discord.'

    embed = attr()
    if message.title:
      embed.title = message.title
    if message.subtitle:
      embed.description = message.subtitle
    if message.fields:
      embed.fields = [{'name': n, 'value': v} for (n, v) in message.fields.items()]
    if message.summary:
      embed.footer = {'text': message.summary}
    payload = {'embeds': [vars(embed)]}
    res = requests.post(
      self._webhook,
      headers = {'Content-Type': 'application/json'},
      data = json.dumps(payload),
      timeout = self._timeout,
    )
    res.raise_for_status()

class Messenger:
  'Queue and send messages at a regular interval.'

  log_level = logging.INFO

  # how long will we block in queue.get() before giving up
  queue_get_timeout: float = 1.3

  # how long to sleep after successfully sending a message
  send_sleep_interval: float = 3.5

  _services: Sequence[Service]
  _queue: queue.Queue
  _working: bool

  def __init__(
    self,
    services: Sequence[Service],
  ) -> None:

    super().__init__()
    self._services = services
    self._queue = queue.Queue()
    self._working = False

  def send(
    self,
    message: Message,
    **kwargs
  ) -> None:
    'Queue a message to be sent.'

    if not self._working:
      raise RuntimeError('Not started')
    self._queue.put((message, kwargs))

  def _dequeue(self) -> None:
    try:
      message, kwargs = self._queue.get(block=True, timeout=self.queue_get_timeout)
    except queue.Empty:
      return
    log = logger[self.log_level] # type: ignore
    threads = [
      Thread.spawn(
        target=svc.send, args=(message,), kwargs=kwargs, name=type(svc).__name__)
      for svc in self._services
    ]
    for thread in threads:
      thread.join()
      if thread.error:
        log(f'Unhandled exception sending message for {thread.name}:')
        log(format_exc_info(thread.error, prefix='  '))
    self._queue.task_done()
    sleep(self.send_sleep_interval)

  def start(self) -> None:
    'Run the messenger queue loop.'

    log = logger[self.log_level] # type: ignore
    self._working = True
    try:
      log('Messenger starting')
      while self._working:
        self._dequeue()
      if not self._queue.empty():
        log(f'Shutdown, sending {self._queue.qsize()} pending messages...')
        while not self._queue.empty():
          self._dequeue()
    finally:
      log('Messenger stopping')

  def stop(self) -> None:
    '''
    Stop sending messages. New messages via `send()` will not be accepted.
    Pending messages will be sent before the queue loop exits.
    '''

    self._working = False

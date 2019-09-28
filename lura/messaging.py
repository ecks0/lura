'''
Send messages to e.g. ms-teams or discord.

This is a simple api that can accommodate multiple messaging services.

There's also `Messenger` class that will queue outgoing and send messages
on a schedule as to not trigger flood protection on your webhooks.
'''

import queue
import requests
from lura import logs
from lura import threads
from lura.attrs import attr
from lura.formats import json
from lura.time import poll
from time import sleep

logger = logs.get_logger(__name__)

def teams(webhook, title='', subtitle='', summary='', fields={}, timeout=20.0):
  'Send a message to MS Teams.'

  payload = {
    '@type': 'MessageCard',
    '@context': 'http://schema.org/extensions',
    'summary': summary, # XXX what does this actually do?
    'sections': [
      {
        'activityTitle': title,
        'activitySubtitle': subtitle,
        'facts': [{'name': n, 'value': v} for (n, v) in fields.items()]
      }
    ]
  }
  headers = {'Content-Type': 'application/json'}
  res = requests.post(
    webhook, headers=headers, data=json.dumps(payload), timeout=timeout)
  try:
    res.raise_for_status()
    return None
  except requests.exceptions.HTTPError:
    return res

def discord(
  webhook, title=None, subtitle=None, summary=None, fields={}, timeout=20.0
):
  'Send a message to Discord.'

  embed = attr()
  if title:
    embed.title = title
  if subtitle:
    embed.description = subtitle
  if fields:
    fields = [{'name': n, 'value': v} for (n, v) in fields.items()]
    embed.fields = fields
  if summary:
    embed.footer = {'text': summary}
  payload = {'embeds': [embed]}
  headers = {'Content-Type': 'application/json'}
  res = requests.post(
    webhook, headers=headers, data=json.dumps(payload), timeout=timeout)
  try:
    res.raise_for_status()
    return None
  except requests.exceptions.HTTPError:
    return res

class Messenger:
  '''
  This class queues messages for teams and discord and sends them a regular
  interval so as to not trigger flood protection. Create an instance and call
  `start()` to execute the main loop.
  '''

  log_level = logger.INFO

  _senders = {'teams': teams, 'discord': discord}

  # how long will we block in queue.get() before giving up
  _queue_get_timeout = 5

  def __init__(self, teams_webhook=None, discord_webhook=None, pulse=4.0):
    super().__init__()
    self._webhooks = {
      'teams': teams_webhook,
      'discord': discord_webhook,
    }
    self._pulse = pulse
    self._queue = queue.Queue()
    self._working = False

  def is_idle(self):
    return self._queue.empty()

  idle = property(is_idle)

  def wait_for_idle(self, timeout):
    return poll(self.is_idle, timeout=timeout, pause=1)

  def send(self, **kwargs):
    self._queue.put(kwargs)

  def _send(self, kwargs):
    'Send the message with all configured services.'

    log = logger[self.log_level]
    sent = False
    for service in 'teams', 'discord':
      webhook = self._webhooks[service]
      if not webhook:
        continue
      send = self._senders[service]
      try:
        res = send(webhook, **kwargs)
        if res is None:
          sent = True
      except Exception:
        log(f'Unhandled exception for {service} message', exc_info=True)
    return sent

  def _run(self):
    'Get a set of kwargs from the queue and try to send them.'

    try:
      kwargs = self._queue.get(block=True, timeout=self._queue_get_timeout)
    except queue.Empty:
      return
    try:
      sent = self._send(kwargs)
    finally:
      self._queue.task_done()
    if sent:
      sleep(self._pulse)

  def _loop(self):
    'Run the work loop.'

    while self._working:
      self._run()

  def work(self):
    'Main entry point for the messaging work loop.'

    log = logger[self.log_level]
    self._working = True
    log('Messenger starting')
    try:
      self._loop()
    except Exception:
      log(f'Unhandled exception in messenger', exc_info=True)
      raise
    finally:
      log('Messenger stopping')

  start = work

  def stop(self):
    'Break the work loop.'

    self._working = False

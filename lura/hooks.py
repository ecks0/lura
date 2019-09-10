import sys
import traceback
from lura import logs

log = logs.get_logger(__name__)

class Hooks:

  def __init__(
    self,
    hooks = None,
  ):
    log.noise(f'__init__({self}, {hooks})')
    super().__init__()
    self.hooks = []
    if hooks:
      self.hooks.extend(hooks)

  def __iter__(self):
    log.noise('__iter__()')
    return self.hooks.__iter__()

  def handler(self, source, hook, signal, ev):
    log.noise(f'handler({self}, {source}, {signal}, {ev})')
    return getattr(hook, signal, None)

  def format_error(self, source, hook, signal, ev):
    log.noise(f'format_error({self})')
    msg = msg = "Hook '{}' raised exception for signal '{}', event '{}'"
    return msg.format(hook, signal, ev)

  def error(self, source, hook, signal, ev):
    log.noise(f'error({self}, {source}, {hook}, {signal}, {ev})')
    log.exception(self.format_error(source, hook, signal, ev))

  def missing(self, source, hook, signal, ev):
    log.noise(f'missing({self}, {source}, {hook}, {signal}, {ev})')
    # noop

  def __getattr__(self, signal):
    log.noise(f'__getattr__({self}, {signal})')
    def dispatch(source, ev, *args, **kwargs):
      log.noise(f'dispatch({source}, {ev})')
      for hook in self.hooks:
        fn = self.handler(source, hook, signal, ev)
        if not fn:
          self.missing(source, hook, signal, ev)
          continue
        try:
          fn(source, ev, *args, **kwargs)
        except Exception:
          self.error(source, hook, signal, ev)
    return dispatch

  def add(self, hook):
    log.noise(f'add({self}, {hook})')
    if hook not in self.hooks:
      self.hooks.append(hook)

  def remove(self, hook):
    log.noise(f'remove({self}, {hook})')
    if hook in self.hooks:
      self.hooks.remove(hook)

  def clear(self):
    log.noise(f'clear({self})')
    self.hooks.clear()

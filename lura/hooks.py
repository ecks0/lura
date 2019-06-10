import sys
import traceback

class Hooks:

  def __init__(
    self,
    hooks = None,
  ):
    super().__init__()
    self.hooks = []
    if hooks:
      self.hooks.extend(hooks)

  def __iter__(self):
    return self.hooks.__iter__()

  def handler(self, source, hook, signal, ev):
    return getattr(hook, signal, None)

  def format_error(self, source, hook, signal, ev):
    msg = msg = "Hook '{}' raised exception for signal '{}', event '{}'"
    return msg.format(hook, signal, ev)

  def error(self, source, hook, signal, ev):
    print(self.format_error(source, hook, signal, ev), file=sys.stderr)
    traceback.print_exc()

  def missing(self, source, hook, signal, ev):
    # noop
    pass

  def __getattr__(self, signal):
    def dispatch(source, ev, *args, **kwargs):
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
    if hook not in self.hooks:
      self.hooks.append(hook)

  def remove(self, hook):
    if hook in self.hooks:
      self.hooks.remove(hook)

  def clear(self):
    self.hooks.clear()

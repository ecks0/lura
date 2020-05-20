from typing import Any, Dict, MutableMapping, TYPE_CHECKING, Union

class attr:
  '''
  Wrap dictionaries and expose their keys as attributes. Nested dictionaries
  are auto-wrapped in an `attr` when accessed, and unwrapped from an `attr`
  when set.

  Example 1, wrapping a dict:

    > d = dict(foo=123, bar='abc', baz=dict(zab='xyz'))
    > a = attr(d)
    > a.foo
    123
    > a.bar
    'abc'
    > a.baz.zab
    'xyz'
    > a.baz.oof = dict(rab=321)
    > a.baz.oof.rab
    321
    > d['baz']['oof']['rab']
    321

  Example 2, constructor-supplied dict:

    > a = attr(foo=123, bar='abc', baz=dict(zab='xyz'))
    > a.baz.zab
    'xyz'
  '''

  __slots__ = ('__wrapped__',)
  # we could use __dict__ but we don't always want to initialize a new one,
  # e.g. when the user provides a backing dict. using a slot lets us choose

  __wrapped__: MutableMapping

  def __init__(
    self,
    *args: Union[MutableMapping, 'attr'],
    **kwargs: Any
  ) -> None:

    super().__init__()
    if args and kwargs:
      raise ValueError('args and kwargs are mutually exclusive')
    if len(args) > 1:
      raise ValueError(f'Accepts 1 positional argument, received {len(args)}')
    src = args[0] if args else None
    if isinstance(src, MutableMapping):
      wrapped = src
    elif isinstance(src, attr):
      wrapped = dict(src.__wrapped__)
    elif src is None:
      wrapped = {
        k: v.__wrapped__ if isinstance(v, attr) else v
        for (k, v) in kwargs.items()
      }
    else:
      raise ValueError(f"Unsupported type '{type(src)}' for 'args[0]'")
    super().__setattr__('__wrapped__', wrapped)

  if TYPE_CHECKING:
    __dict__: Dict[str, Any] = {}
  else:
    @property
    def __dict__(self) -> Dict[str, Any]:
      'Return the wrapped dictionary.'

      # works with e.g. vars()
      return self.__wrapped__

  def __getattr__(self, name: str) -> Any:
    try:
      value = self.__wrapped__[name]
      return type(self)(value) if isinstance(value, MutableMapping) else value
    except KeyError:
      pass
    raise AttributeError(
      f"'{type(self).__name__}' object has no attribute '{name}'")

  def __setattr__(self, name: str, value: Any) -> None:
    if isinstance(value, attr):
      self.__wrapped__[name] = value.__wrapped__
    else:
      self.__wrapped__[name] = value

'click command-line processing helpers.'

import click
from typing import Any, Optional

class StartsWithGroup(click.Group):
  'Group implementation which will match partial group/command names.'

  def __init__(self, *args: Any, **kwargs: Any) -> None:
    super().__init__(*args, **kwargs)

  def get_command(
    self,
    ctx: click.Context,
    name: str
  ) -> Optional[click.Command]:
  
    res = super().get_command(ctx, name)
    if res is not None:
      return res
    names = [_ for _ in self.list_commands(ctx) if _.startswith(name)]
    if not names:
      return None
    elif len(names) == 1:
      return super().get_command(ctx, names[0])
    names = ', '.join(sorted(names)) # type: ignore
    ctx.fail(f'Too many matches: {names}')

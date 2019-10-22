import click

class StartsWithGroup(click.Group):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

  def get_command(self, ctx, name):
    res = super().get_command(ctx, name)
    if res is not None:
      return res
    names = [_ for _ in self.list_commands(ctx) if _.startswith(name)]
    if not names:
      return None
    elif len(names) == 1:
      return super().get_command(ctx, names[0])
    names = ', '.join(sorted(names))
    ctx.fail(f'Too many matches: {names}')

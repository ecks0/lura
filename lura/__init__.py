from .log import Logging

logs = Logging(
  std_logger = __name__,
  std_format = Logging.formats.bare,
)

del Logging

class LuraError(RuntimeError):

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

from .run import run

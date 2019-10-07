from .log import Logging

logs = Logging(
  std_logger = __name__,
  std_format = Logging.formats.bare,
)

del Logging

from .run import run

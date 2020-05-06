import logging
from lura import logutils

logutils.configure(
  package = __name__,
  format = logutils.formats.hax,
  level = logging.INFO,
)

del logging
del logutils

from types import TracebackType
from typing import Tuple, Type, Union

# type alias for the result of sys.exc_info()
ExcInfo = Union[Tuple[Type[BaseException], BaseException, TracebackType], Tuple[None, None, None]]

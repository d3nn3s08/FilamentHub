class DummyLogger:
    """
Dummy logger that conforms to logging.Logger interface
and discards all log messages.

Used as a fallback when logging is optional.
"""


    def debug(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def exception(self, *args, **kwargs): pass
    def critical(self, *args, **kwargs): pass

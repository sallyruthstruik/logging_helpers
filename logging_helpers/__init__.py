import logging
import threading
from functools import wraps
from logging import handlers

from pip._vendor import six

l = logging.getLogger("root")

class _PatchLogging(object):
    _originals = {}

    def _get_patched(self, func):
        self._originals[func.__name__] = func

        return wraps(func)(lambda *a, **k: LoggerWrapper(func(*a, **k)))

    def __call__(self):
        logging.getLogger = self._get_patched(logging.getLogger)

patch_logging = _PatchLogging()

class _Context(object):
    _context = threading.local()

    def __init__(self):
        if not hasattr(self._context, "data"):
            self._context.data = {}

    def addContext(self, data):
        for key, value in six.iteritems(data):
            self._context.data[key] = value

    def getContext(self):
        return self._context.data

global_context = _Context()

class Mutator(object):
    """
    Mutators allows you easily manage each log record before emit
    """

    def mutate(self, record):
        raise NotImplementedError

RESERVED_KEYWORDS = [
    "exc_info",
    "extra",
    "args",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "thread",
    "threadName"
]

class KeyValueMutator(object):

    def mutate(self, record):
        pairs = []

        for key, value in six.iteritems(record.__dict__):
            if key not in RESERVED_KEYWORDS:
                pairs.append([key, value])

        print pairs
        if pairs:
            pairs.sort(key=lambda k: k[0])

        record.msg += " "+", ".join(
            "{}=%s".format(key)
            for key, _ in pairs
        )
        record.args += tuple(
            v for _, v in pairs
        )

        return record



class LoggerWrapper(logging.Logger):

    def __init__(self, originalLogger):
        self.originalLogger = originalLogger
        self.mutators = []  #type: list[Mutator]


        #patch handle
        self._originalHandle = self.originalLogger.handle
        self.originalLogger.handle = self.handle

    def addMutator(self, mutator):
        self.mutators.append(mutator)

    def critical(self, msg, *args, **kwargs):
        super(LoggerWrapper, self).critical(msg, *args, **kwargs)

    def _log(self, level, msg, args, **kwargs):
        exc_info = kwargs.pop("exc_info", None)
        extra = kwargs.pop("extra", {})

        for key, value in six.iteritems(global_context.getContext()):
            extra[key] = value

        extra.update({
            key:value for key, value in six.iteritems(kwargs) if key not in RESERVED_KEYWORDS
        })

        self.originalLogger._log(level, msg, args, exc_info, extra)

    def handle(self, record):
        for m in self.mutators:
            record = m.mutate(record)

        self._originalHandle(record)

    def log(self, level, msg, *args, **kwargs):
        super(LoggerWrapper, self).log(level, msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        super(LoggerWrapper, self).info(msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        super(LoggerWrapper, self).debug(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        super(LoggerWrapper, self).warning(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        super(LoggerWrapper, self).exception(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        super(LoggerWrapper, self).error(msg, *args, **kwargs)

    def getChild(self, suffix):
        return LoggerWrapper(self.originalLogger.getChild(suffix))

    def __getattr__(self, item):
        return getattr(self.originalLogger, item)
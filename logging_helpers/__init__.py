import copy
import logging
import threading
from functools import wraps
from logging import handlers, raiseExceptions
from logging import CRITICAL, INFO, DEBUG, WARN, WARNING, ERROR
from pip._vendor import six

l = logging.getLogger("root")

class _PatchLogging(object):
    _originals = {}

    def _get_patched(self, func):
        if func.__name__ in self._originals:
            return func

        self._originals[func.__name__] = func

        return wraps(func)(lambda *a, **k: LoggerWrapper.fromLogger(func(*a, **k)))

    def __call__(self):
        logging.getLogger = self._get_patched(logging.getLogger)

patch_logging = _PatchLogging()

class _Context(object):
    _context = threading.local()

    def __init__(self):
        self.mutators = []
        self._check_data()

    def _check_data(self):
        if not hasattr(self._context, "data"):
            self._context.data = {}

    def addContext(self, data):
        self._check_data()

        for key, value in six.iteritems(data):
            self._context.data[key] = value

    def addMutator(self, mutator):
        assert isinstance(mutator, Mutator)

        self.mutators.append(mutator)

    def getContext(self):
        self._check_data()
        return self._context.data

    def getMutators(self):
        return self.mutators

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
    "threadName",
    "stack_info"
]

class KeyValueMutator(Mutator):
    DELIMITER = "\n"
    def mutate(self, record):
        pairs = []

        for key, value in six.iteritems(record.__dict__):
            if key not in RESERVED_KEYWORDS:
                pairs.append([key, value])

        if pairs:
            pairs.sort(key=lambda k: k[0])

        record.msg += " "+self.DELIMITER.join(
            "{}=%s".format(key)
            for key, _ in pairs
        )

        acc = tuple(
            v for _, v in pairs
        )
        if not isinstance(record.args, tuple):
            record.args = (record.args, ) + acc
        else:
            record.args += acc

        return record



class LoggerWrapper(logging.Logger):

    cache = {}

    @classmethod
    def fromLogger(cls, logger):
        cls.cache.setdefault(id(logger), cls(logger))
        return cls.cache[id(logger)]

    def __init__(self, originalLogger):
        self.originalLogger = originalLogger
        self.mutators = []  #type: list[Mutator]

        #patch handle
        self._originalHandle = self.originalLogger.handle

        @wraps(self.originalLogger.handle)
        def patched_handle(record):
            record = copy.copy(record)

            for m in self.getMutators():
                record = m.mutate(record)
            return self._originalHandle(record)

        patched_handle._is_patched_handle = True

        if not hasattr(self.originalLogger.handle, "_is_patched_handle"):
            self.originalLogger.handle = patched_handle

    def addMutator(self, mutator):
        self.mutators.append(mutator)

    def getMutators(self):
        return global_context.getMutators() + self.mutators

    def critical(self, msg, *args, **kwargs):
        if self.isEnabledFor(CRITICAL):
            self._log(CRITICAL, msg, args, **kwargs)

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
        return self.originalLogger.handle(record)

    def log(self, level, msg, *args, **kwargs):
        if not isinstance(level, int):
            if raiseExceptions:
                raise TypeError("level must be an integer")
            else:
                return
        if self.isEnabledFor(level):
            self._log(level, msg, args, **kwargs)

    def info(self, msg, *args, **kwargs):
        if self.isEnabledFor(INFO):
            self._log(INFO, msg, args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        if self.isEnabledFor(DEBUG):
            self._log(DEBUG, msg, args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        if self.isEnabledFor(WARNING):
            self._log(WARNING, msg, args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        kwargs['exc_info'] = 1
        self.error(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        if self.isEnabledFor(ERROR):
            self._log(ERROR, msg, args, **kwargs)

    def getChild(self, suffix):
        return LoggerWrapper.fromLogger(self.originalLogger.getChild(suffix))

    def removeHandler(self, hdlr):
        self.originalLogger.removeHandler(hdlr)

    def isEnabledFor(self, level):
        return self.originalLogger.isEnabledFor(level)

    def setLevel(self, level):
        return self.originalLogger.setLevel(level)

    def getEffectiveLevel(self):
        return self.originalLogger.getEffectiveLevel()

    def callHandlers(self, record):
        return self.originalLogger.callHandlers(record)

    def addHandler(self, hdlr):
        return self.originalLogger.addHandler(hdlr)

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info, func=None, extra=None):
        return self.originalLogger.makeRecord(name, level, fn, lno, msg, args, exc_info, func, extra)

    def findCaller(self):
        return self.originalLogger.findCaller()

    def __getattr__(self, item):
        return getattr(self.originalLogger, item)

from .django_middleware import DjangoRequestLog
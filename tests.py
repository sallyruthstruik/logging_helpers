# coding=utf-8
import logging
from threading import Event, Thread

import pytest

from logging_helpers import patch_logging, LoggerWrapper, KeyValueMutator, global_context


def test_patching():
    patch_logging()
    assert type(logging.getLogger("root")) is LoggerWrapper
    assert type(logging.getLogger("some.test")) is LoggerWrapper
    assert type(logging.getLogger("some").getChild("other")) is LoggerWrapper

@pytest.fixture
def handler():
    queue = []

    class Handler(logging.StreamHandler):
        def handle(self, record):
            msg = self.format(record)
            queue.append(msg)

    return Handler(), queue

@pytest.fixture
def logger(handler):
    KeyValueMutator.DELIMITER = ", "
    handler, queue = handler

    l = logging.getLogger("root")
    l.addHandler(handler)

    return l, queue

def test_passing_extra(logger):
    logger, queue = logger

    logger.warning("Message", key="value", nested={"inner": 123})
    assert queue[0] == "Message"


def test_auto_extra_renderer(logger):
    logger, queue = logger

    assert isinstance(logger, LoggerWrapper)
    logger.addMutator(KeyValueMutator())

    logger.warning("Message", key="value", nested={"inner": 123})
    assert queue[-1] == "Message key=value, nested={'inner': 123}"

def test_global_mutator(handler):
    h, q = handler

    logger = logging.getLogger("olala")
    assert logger.mutators == []
    logger.addHandler(h)

    global_context.addMutator(KeyValueMutator())

    logger.error("Message", key=1)
    assert q[-1] == "Message key=1"

@pytest.mark.target
def test_dictconfig_with_patch():

    patch_logging()
    from logging.config import dictConfig

    dictConfig({
        "version": 1,
        "handlers": {
            'default': {
                'level': 'NOTSET',
                'class': 'logging.StreamHandler'
            },
        },

        "loggers": {
            "": {
                'handlers': ["default"],
                'level': 'INFO',
                'propagate': False,
            }
        }
    })

    assert logging.getLogger("olala").originalLogger.isEnabledFor(logging.INFO)


def test_logger_context(handler):
    handler, queue = handler

    e1 = Event()
    e2 = Event()

    def thread1():
        global_context.addContext({
            "id": 1
        })
        global_context.addMutator(KeyValueMutator())

        l = logging.getLogger("root")

        l.addHandler(handler)
        l.error("Message", key=1)
        assert queue[-1] == "Message id=1, key=1"

        e1.wait()

        l.error("Message", key=3)
        assert queue[-1] == "Message id=1, key=3"

        e2.set()

    def thread2():
        global_context.addContext({
            "id": 2
        })
        global_context.addMutator(KeyValueMutator())

        l = logging.getLogger("root")
        l.addHandler(handler)
        l.error("Message", key=2)

        assert queue[-1] == "Message id=2, key=2"

        e1.set()
        e2.wait()

        l.error("Message", key=4)
        assert queue[-1] == "Message id=2, key=4"

    t1 = Thread(target=thread1)
    t2 = Thread(target=thread2)

    t1.start()
    t2.start()

    t1.join()
    t2.join()





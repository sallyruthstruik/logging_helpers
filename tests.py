# coding=utf-8
import logging

import pytest

from logging_helpers import patch_logging, LoggerWrapper, KeyValueMutator


def test_patching():
    patch_logging()
    assert type(logging.getLogger("root")) is LoggerWrapper
    assert type(logging.getLogger("some.test")) is LoggerWrapper
    assert type(logging.getLogger("some").getChild("other")) is LoggerWrapper



@pytest.fixture
def logger():
    queue = []

    class Handler(logging.StreamHandler):
        def handle(self, record):
            msg = self.format(record)
            queue.append(msg)

    l = logging.getLogger("root")
    l.addHandler(Handler())

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

    logger.warning("Message", key="value", nested={u"Привет мир!": u"Привет"})
    assert queue[-1] == "Message key=value, nested={u'Привет мир!': u'Привет'}"





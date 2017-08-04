# coding=utf-8
import logging
from logging import Logger
from threading import Event, Thread

import pytest
import sys

from logging_helpers import patch_logging, LoggerWrapper, KeyValueMutator, global_context


def test_patching():
    patch_logging()
    assert type(logging.getLogger("root")) is LoggerWrapper
    assert type(logging.getLogger("some.test")) is LoggerWrapper
    assert type(logging.getLogger("some").getChild("other")) is LoggerWrapper
    assert type(logging.getLogger("root").originalLogger) is Logger

    #second patch has no effect
    patch_logging()

    assert type(logging.getLogger("root").originalLogger) is Logger


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
    patch_logging()

    KeyValueMutator.DELIMITER = ", "
    handler, queue = handler

    l = logging.getLogger("root")
    l.addHandler(handler)
    l.setLevel("INFO")
    l.mutators = []

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


    if sys.version_info[0] < 3:
        #test unicode rendering
        logger.error(
            "Error validating invoice: %s", "Отклонено: вы уже зашли под юзером",
            headers="{u'CONTENT_TYPE': u'multipart/form-data; boundary=BoUnDaRyStRiNg; charset=utf-8', u'HTTP_COOKIE': u' csrftoken=VZKpG9EaqJXD0IV0TDnpFZeT2KEhwv6p; expires=Thu, 12-Jul-2018 12:38:07 GMT; Max-Age=31449600; Path=/;  sessionid=pctzehk2ohqza9qn5ry8qwsx0koieuss; expires=Thu, 13-Jul-2017 13:38:06 GMT; httponly; Max-Age=3600; Path=/', u'wsgi.multithread': False, u'SCRIPT_NAME': u'', u'wsgi.input': <django.test.client.FakePayload object at 0x7f63b57b1890>, u'REQUEST_METHOD': u'POST', u'PATH_INFO': u'/api/2/cabinet/accept_login_as_invoice', u'SERVER_PROTOCOL': 'HTTP/1.1', u'QUERY_STRING': u'', u'CONTENT_LENGTH': 152, 'HTTP_USER_AGENT': 'Olala', u'wsgi.version': (1, 0), 'HTTP_REFERER': 'https://cab.coin32.com/', u'SERVER_NAME': 'testserver', u'REMOTE_ADDR': '127.0.0.1', u'wsgi.run_once': False, u'wsgi.errors': <_io.BytesIO object at 0x7f63d43c0d70>, u'wsgi.multiprocess': True, u'wsgi.url_scheme': 'http', 'HTTP_X_FORWARDED_FOR': '127.0.0.1', u'SERVER_PORT': '80', u'CSRF_COOKIE': u'VZKpG9EaqJXD0IV0TDnpFZeT2KEhwv6p', u'CSRF_COOKIE_USED': True}",
            invoice='<LoginAsInvoice: LoginAsInvoice(id=4, admin=test@1.ru[1050], user=test@2.ru[1051], user_agent=Olala, ip=127.0.0.1)>',
            method=u'POST',
            request_id='3907e531041344f1b7952d4f7efe053e',
            request_ip='127.0.0.1',
            url=u'/api/2/cabinet/accept_login_as_invoice'
        )
        assert q[-1].startswith("Error validating")


@pytest.mark.target
def test_dictconfig_with_patch():

    patch_logging()
    from logging.config import dictConfig

    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
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

@pytest.mark.test_logger_bind
def test_logger_bind(logger):

    logger, q = logger

    global_context.addMutator(KeyValueMutator())

    assert isinstance(logger, LoggerWrapper)
    bindedLogger = logger.bind(key="value")
    bindedLogger.info("Olala")
    assert q[-1] == "Olala key=value"

    logger.info("Olala")
    assert q[-1] == "Olala"

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


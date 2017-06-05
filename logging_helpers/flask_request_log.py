import logging

try:
    import urlparse
except:
    from urllib import parse as urlparse
from uuid import uuid4

import time
from flask.globals import request

from logging_helpers import global_context


def request_log_before_request():

    try:
        json = request.json or request.data
    except: #pylint: disable=bare-except
        json = request.data

    ipaddr = request.headers.get("X-Real-Ip") or request.remote_addr

    global_context.addContext(dict(
        request_ip=ipaddr,
        url=urlparse.urlparse(request.url).path,
        method=request.method,
        request_id=uuid4().hex
    ))

    logging.getLogger("request_log").info(
        "New request",
        remote_addr=request.remote_addr,
        query_params=request.args,
        body=json,
        headers=dict(request.headers),
    )

    #pylint: disable=protected-access
    request._start = time.time()

def request_log_after_request(response):
    """
    :type response: flask.wrappers.Response
    """

    duration = None
    if hasattr(request, "_start"):
        #pylint: disable=protected-access
        duration = time.time() - request._start

    responseText = None
    if response.status_code > 300:
        responseText = response.data

    logging.getLogger("request_log").info(
        "Response",
        status_code=response.status_code,
        duration=duration,
        text=responseText
    )

    return response
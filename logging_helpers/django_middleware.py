import json

try:
    import urlparse
except:
    from urllib import parse as urlparse

import time

import logging
from uuid import uuid4

from logging_helpers import global_context

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

class DjangoRequestLog(object):

    def process_request(self, request):

        global_context.addContext(dict(
            request_ip=get_client_ip(request),
            url=urlparse.urlparse(request.get_full_path()).path,
            method=request.method,
            request_id=uuid4().hex
        ))

        request._request_stat_middleware_start_ts = time.time()

        curlString = "curl -v -X{method} {body} --cookie \"{cookie}\" http://{host}{url}".format(
            method=request.method.upper(),
            body="-d \"{}\"".format(json.dumps(request.body)) if (
                request.body and request.META.get("CONTENT_TYPE") == "application/json"
            ) else "",
            cookie=request.META.get("HTTP_COOKIE", ""),
            url=request.get_full_path(),
            host=request.get_host()
        )

        logging.getLogger("request_log").info(
            "New request", **{
                "method": request.method,
                "body": request.body[:2000],
                "curl": curlString,
                "GET": dict(request.GET),
                "headers": {
                    key: value
                    for key, value in request.META.iteritems()
                    if key.startswith("HTTP_")
                }
            }
        )

    def process_response(self, request, response):
        """
        :type request: django.http.request.HttpRequest
        :type response: django.http.response.HttpResponse
        :return:
        """

        url = urlparse.urlparse(request.get_full_path()).path
        duration = time.time() - request._request_stat_middleware_start_ts

        user = request.user if hasattr(request, "user") else None

        if response.status_code > 210:
            logging.getLogger("request_log").warning(
                "Finished request",
                duration=duration,
                user=user,
                status_code=response.status_code,
                response=response.content[:1000]
            )
        else:
            logging.getLogger("request_log").info(
                "Finished request",
                duration=duration,
                user=user,
                status_code=response.status_code
            )

        return response
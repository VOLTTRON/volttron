# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

"""
This module is used to process asynchronous requests and cache results for later
use.  It was written to handle Web API calls to the Chargepoint service but could
be used for any long-ish running, gevent friendly function calls.

A single queue is managed by the web_service() function.  Requests are placed on
the queue by client code, usually with a call to CPRequest.request().  The web_service()
function records the request in a dictionary using the method signature (name + parameters).
This dictionary maintains a set of AsyncResult objects, one for each request with the same
signature.

After recording the request in the dictionary, the web_service() executes the request method
in a short-lived greenlet (web_call()).  The response is placed on the queue.  When the
web_service() encounters a response, it sets the values of all the AsyncResults waiting on
that request, causing the client greenlets to 'wake-up' on an AsyncResult.wait().

The request and response is left in the dictionary until a configurable expiration
time so that subsequent requests with the same signature can use the cached result
if it has not expired.  In this case, the AsyncResult is set immediately.

"""
from __future__ import print_function
import gevent
import gevent.event
import gevent.queue
import logging
import suds
from gevent import monkey
from .service import CPAPIException
from datetime import datetime, timedelta

monkey.patch_all()
_log = logging.getLogger(__name__)
SERVICE_WSDL_URL = "https://webservices.chargepoint.com/cp_api_5.0.wsdl"

# Queue for Web API requests and responses.  It is managed by the long running
# web_service() greenlet.
web_service_queue = gevent.queue.Queue()


class CPRequest (object):
    """ Encapsulates a method to be called asynchronously.

        The result is returned as AsyncResult.  The request() classmethod is used to
        create a request, queue it to the web_service() and return
        an AsyncResult that the caller can wait() on.

    """

    def __init__(self, method, timeout, *args, **kwargs):
        """
        Stores the method+params and creates a new AsyncResult.

        @param method: A callable that will run in its own greenlet.
        @param args:
        @param kwargs
        """
        self._method = method
        self._client = method.__self__._client
        self._timeout = timeout
        self._args = args
        self._kwargs = kwargs
        self._sent = None
        self._received = None
        self._response = None
        self._result = gevent.event.AsyncResult()

    @property
    def timeout(self):
        return self._timeout

    def __str__(self):
        return self.key()

    def is_request(self):
        return True

    def key(self):
        return self._method.__str__() + self._args.__str__() + self._kwargs.__str__()

    def result(self):
        return self._result

    @classmethod
    def request(cls, method, timeout, *args, **kwargs):
        """Generate a new request and put it on the web service queue.

           Returns the requests AsyncResult instance which will be
           filled in after the request has been executed.

        """
        global web_service_queue
        r = CPRequest(method, timeout, *args, **kwargs)

        web_service_queue.put(r)
        return r.result()


class CPResponse (object):
    """A response to to a CPRequest invocation.


    """

    def __init__(self, key, response, client):
        """

        """
        self._key = key
        self._response = response
        self._client = client

    def __str__(self):
        return 'Response to: {}'.format(self._key)

    def key(self):
        return self._key

    def is_request(self):
        return False

    def response(self):
        return self._response

    @property
    def client(self):
        return self._client


def web_call(request, client):
    """Wraps the request to be executed.

        This is spawned as a greenlet and puts the
        request result on the queue.
    """
    global web_service_queue
    try:
        request._method.__self__.set_client(client)
        response = request._method(*request._args, **request._kwargs)
    except CPAPIException as exception:
        _log.warning(exception)
        response = exception

    web_service_queue.put(CPResponse(request.key(), response, client))


class CacheItem (object):
    """A cached request/response.

        As responses come in, they are matched to the originating request
        and waiting_results are 'set'.  Subsequent requests with the same signature (key)
        are satisfied immediately, if not expired,  by setting the async result on the incoming
        request.
    """

    def __init__(self, cache_life):
        self._request = None
        self._response = None
        self._waiting_results = set()
        self._expiration = datetime.utcnow() + timedelta(seconds=cache_life)

    @property
    def request(self):
        return self._request

    @request.setter
    def request(self, r):
        self._request = r

    @property
    def response(self):
        return self._response

    @response.setter
    def response(self, r):
        self._response = r

    @property
    def waiting_results(self):
        return self._waiting_results

    @property
    def expiration(self):
        return self._expiration


def web_service():
    """Cache/service request loop.

       Reads items from the web_service_queue.  It is intended to be spawned as a greenlet
         that runs forever.

       If the de-queued item is a CPRequest, the cache is checked for an existing response.
       If not found, the request is added to cache and a greenlet is spawned to complete the request.

       If the de-queued item is a CPResponse, the item is found in cache and all waiting
       AsyncResults are set with the response.  The response will stay in cache until expiration.

    """

    global web_service_queue
    web_cache = dict()
    client_set = set()

    for item in web_service_queue:
        if item.is_request():
            # Item is a request to make an async call.

            item_key = item.key()
            # _log.info("START {0}".format(item_key))
            # First deal with expiration, popping anything that is too old.
            if item_key in web_cache and web_cache[item_key].expiration < datetime.utcnow():
                web_cache.pop(item_key)
            cached_request = web_cache.get(item_key, None)
            if cached_request:
                # Found item, use it
                # _log.info("FOUND {0}".format(cached_request))
                if cached_request.response:
                    item.result().set(cached_request.response)
                else:
                    # Still waiting for response, add this one
                    web_cache[item_key].waiting_results.add(item.result())
                del item
            else:
                # New request
                # _log.info("MISSED {0}".format(cached_request))
                cache_item = CacheItem(item.timeout)
                cache_item.request = item
                cache_item.waiting_results.add(item.result())
                web_cache[item_key] = cache_item

                if not client_set:
                    client_set.add(suds.client.Client(SERVICE_WSDL_URL))
                client = client_set.pop()
                gevent.spawn(web_call, item, client)

        else:  # Handle response

            cached_request = web_cache.get(item.key())
            cached_request.response = item.response()
            for result in cached_request.waiting_results:
                result.set(cached_request.response)
            client_set.add(item.client)
            cached_request.waiting_results.clear()

# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}
import inspect
import os
import re

from watchdog.events import PatternMatchingEventHandler
import logging

_log = logging.getLogger(__name__)


def get_random_key(length: int = 65) -> str:
    """
    Returns a hex random key of specified length.  The length must be > 0 in order for
    the key to be valid.  Raises a ValueError if the length is invalid.

    The default length is 65, which is 130 in length when hexlify is run.

    :param length:
    :return:
    """
    if length <= 0:
        raise ValueError("Invalid length specified for random key must be > 0")

    import binascii
    random_key = binascii.hexlify(os.urandom(length)).decode('utf-8')
    return random_key


def is_ip_private(vip_address):
    """ Determines if the passed vip_address is a private ip address or not.

    :param vip_address: A valid ip address.
    :return: True if an internal ip address.
    """
    ip = vip_address.strip().lower().split("tcp://")[1]

    # https://en.wikipedia.org/wiki/Private_network

    priv_lo = re.compile(r"^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_24 = re.compile(r"^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_20 = re.compile(r"^192\.168\.\d{1,3}.\d{1,3}$")
    priv_16 = re.compile(r"^172.(1[6-9]|2[0-9]|3[0-1]).[0-9]{1,3}.[0-9]{1,3}$")

    return priv_lo.match(ip) is not None or priv_24.match(
        ip) is not None or priv_20.match(ip) is not None or priv_16.match(
        ip) is not None


def get_hostname():
    with open('/etc/hostname') as fp:
        hostname = fp.read().strip()

    assert hostname
    return hostname

def monkey_patch():
    from gevent import monkey

    # At this point these are the only things that need to be patched
    # and the server and client are working harmoniously with this.
    patches = [
        ('ssl', monkey.patch_ssl),
        ('socket', monkey.patch_socket),
        ('os', monkey.patch_os),
    ]

    # patch modules if necessary.  Only if the module hasn't been patched before.
    # this could happen if the server code uses the client (which it does).
    for module, fn in patches:
        if not monkey.is_module_patched(module):
            fn()

class VolttronHomeFileReloader(PatternMatchingEventHandler):
    """
    Extends PatternMatchingEvent handler to watch changes to a singlefile/file pattern within volttron home.
    filetowatch should be path relative to volttron home.
    For example filetowatch auth.json with watch file <volttron_home>/auth.json.
    filetowatch *.json will watch all json files in <volttron_home>
    """
    def __init__(self, filetowatch, callback):
        # Protect from circular reference for file
        from volttron.platform import get_home

        super(VolttronHomeFileReloader, self).__init__([get_home() + '/' + filetowatch])
        _log.debug("patterns is {}".format([get_home() + '/' + filetowatch]))
        self._callback = callback

    def on_closed(self, event):
        _log.debug("Calling callback on event {}. Calling {}".format(event, self._callback))
        try:
            self._callback()
        except BaseException as e:
            _log.error("Exception in callback: {}".format(e))
        _log.debug("After callback on event {}".format(event))


class AbsolutePathFileReloader(PatternMatchingEventHandler):
    """
    Extends PatternMatchingEvent handler to watch changes to a singlefile/file pattern within volttron home.
    filetowatch should be path relative to volttron home.
    For example filetowatch auth.json with watch file <volttron_home>/auth.json.
    filetowatch *.json will watch all json files in <volttron_home>
    """
    def __init__(self, filetowatch, callback):
        super(AbsolutePathFileReloader, self).__init__([filetowatch])
        self._callback = callback
        self._filetowatch = filetowatch

    @property
    def watchfile(self):
        return self._filetowatch

    def on_closed(self, event):
        _log.debug("Calling callback on event {}. Calling {}".format(event, self._callback))
        try:
            self._callback(self._filetowatch)
        except BaseException as e:
            _log.error("Exception in callback: {}".format(e))
        _log.debug("After callback on event {}".format(event))


def print_stack():
    """
    Utility function to print the full frames stack of a function call.

    The format of the stack is filename->function:lineno
    """
    called = 0
    for x in inspect.stack():
        _log.debug(f"stack: [{called}] {x.filename}->{x.function}:{x.lineno}")
        called += 1

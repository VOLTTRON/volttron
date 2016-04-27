# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#}}}

'''VOLTTRON platform™ agent helper classes/functions.'''

import argparse
from dateutil.parser import parse
from datetime import datetime, timedelta
import errno
import logging
import os
import pytz
import re
import stat
import sys
import syslog
import traceback

import gevent

from zmq.utils import jsonapi

from ..lib.inotify.green import inotify, IN_MODIFY

__all__ = ['load_config', 'run_agent', 'start_agent_thread']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2015, Battelle Memorial Institute'
__license__ = 'FreeBSD'


_comment_re = re.compile(
        r'((["\'])(?:\\?.)*?\2)|(/\*.*?\*/)|((?:#|//).*?(?=\n|$))',
        re.MULTILINE | re.DOTALL)


_log = logging.getLogger(__name__)

def _repl(match):
    '''Replace the matched group with an appropriate string.'''
    # If the first group matched, a quoted string was matched and should
    # be returned unchanged.  Otherwise a comment was matched and the
    # empty string should be returned.
    return match.group(1) or ''


def strip_comments(string):
    '''Return string with all comments stripped.

    Both JavaScript-style comments (//... and /*...*/) and hash (#...)
    comments are removed.
    '''
    return _comment_re.sub(_repl, string)


def load_config(config_path):
    '''Load a JSON-encoded configuration file.'''
    return jsonapi.loads(strip_comments(open(config_path).read()))


def run_agent(cls, subscribe_address=None, publish_address=None,
              config_path=None, **kwargs):
    '''Instantiate an agent and run it in the current thread.

    Attempts to get keyword parameters from the environment if they
    are not set.
    '''
    if not subscribe_address:
        subscribe_address = os.environ.get('AGENT_SUB_ADDR')
    if subscribe_address:
        kwargs['subscribe_address'] = subscribe_address
    if not publish_address:
        publish_address = os.environ.get('AGENT_PUB_ADDR')
    if publish_address:
        kwargs['publish_address'] = publish_address
    if not config_path:
        config_path = os.environ.get('AGENT_CONFIG')
    if config_path:
        kwargs['config_path'] = config_path
    agent = cls(**kwargs)
    agent.run()


def start_agent_thread(cls, **kwargs):
    '''Instantiate an agent class and run it in a new daemon thread.

    Returns the thread object.
    '''
    import threading
    agent = cls(**kwargs)
    thread = threading.Thread(target=agent.run)
    thread.daemon = True
    thread.start()
    return thread


def isapipe(fd):
    fd = getattr(fd, 'fileno', lambda: fd)()
    return stat.S_ISFIFO(os.fstat(fd).st_mode)


def default_main(agent_class, description=None, argv=sys.argv,
                 parser_class=argparse.ArgumentParser, **kwargs):
    '''Default main entry point implementation for legacy agents.

    description and parser_class are depricated. Please avoid using them.
    '''
    try:
        # If stdout is a pipe, re-open it line buffered
        if isapipe(sys.stdout):
            # Hold a reference to the previous file object so it doesn't
            # get garbage collected and close the underlying descriptor.
            stdout = sys.stdout
            sys.stdout = os.fdopen(stdout.fileno(), 'w', 1)

        try:
            sub_addr = os.environ['AGENT_SUB_ADDR']
            pub_addr = os.environ['AGENT_PUB_ADDR']
        except KeyError as exc:
            sys.stderr.write(
                'missing environment variable: {}\n'.format(exc.args[0]))
            sys.exit(1)
        if sub_addr.startswith('ipc://') and sub_addr[6:7] != '@':
            if not os.path.exists(sub_addr[6:]):
                sys.stderr.write('warning: subscription socket does not '
                                 'exist: {}\n'.format(sub_addr[6:]))
        if pub_addr.startswith('ipc://') and pub_addr[6:7] != '@':
            if not os.path.exists(pub_addr[6:]):
                sys.stderr.write('warning: publish socket does not '
                                 'exist: {}\n'.format(pub_addr[6:]))
        config = os.environ.get('AGENT_CONFIG')
        agent = agent_class(subscribe_address=sub_addr,
                            publish_address=pub_addr,
                            config_path=config, **kwargs)
        agent.run()
    except KeyboardInterrupt:
        pass


def vip_main(agent_class, **kwargs):
    '''Default main entry point implementation for VIP agents.'''
    try:
        # If stdout is a pipe, re-open it line buffered
        if isapipe(sys.stdout):
            # Hold a reference to the previous file object so it doesn't
            # get garbage collected and close the underlying descriptor.
            stdout = sys.stdout
            sys.stdout = os.fdopen(stdout.fileno(), 'w', 1)

        # Quiet printing of KeyboardInterrupt by greenlets
        Hub = gevent.hub.Hub
        Hub.NOT_ERROR = Hub.NOT_ERROR + (KeyboardInterrupt,)

        agent_uuid = os.environ.get('AGENT_UUID')
        config = os.environ.get('AGENT_CONFIG')
        agent = agent_class(config_path=config, identity=agent_uuid, **kwargs)
        try:
            run = agent.run
        except AttributeError:
            run = agent.core.run
        task = gevent.spawn(run)
        try:
            task.join()
        finally:
            task.kill()
    except KeyboardInterrupt:
        pass


class SyslogFormatter(logging.Formatter):
    _level_map = {logging.DEBUG: syslog.LOG_DEBUG,
                  logging.INFO: syslog.LOG_INFO,
                  logging.WARNING: syslog.LOG_WARNING,
                  logging.ERROR: syslog.LOG_ERR,
                  logging.CRITICAL: syslog.LOG_CRIT,}

    def format(self, record):
        level = self._level_map.get(record.levelno, syslog.LOG_INFO)
        return '<{}>'.format(level) + super(SyslogFormatter, self).format(record)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        dct = record.__dict__.copy()
        exc_info = dct.pop('exc_info', None)
        if exc_info:
            dct['exc_text'] = ''.join(traceback.format_exception(*exc_info))
        return jsonapi.dumps(dct)


class AgentFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None):
        if fmt is None:
            #fmt = "%(composite_name)s %(levelname)s|[%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
            fmt = '%(asctime)s %(composite_name)s %(levelname)s: %(message)s'
        super(AgentFormatter, self).__init__(fmt=fmt, datefmt=datefmt)

    def composite_name(self, record):
        if record.name == 'agents.log':
            cname = '(%(processName)s %(process)d) %(remote_name)s'
        elif record.name.startswith('agents.std'):
            cname = '(%(processName)s %(process)d) <{}>'.format(
                    record.name.split('.', 2)[1])
        else:
            cname = '() %(name)s'
        return cname % record.__dict__

    def format(self, record):
        if 'composite_name' not in record.__dict__:
            record.__dict__['composite_name'] = self.composite_name(record)
        if len(record.args) > 0 \
            and 'tornado.access' in record.__dict__['composite_name']:
            record.__dict__['msg'] = ','.join([str(b) for b in record.args])
            record.__dict__['args'] = []
        return super(AgentFormatter, self).format(record)


def setup_logging(level=logging.DEBUG):
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        if isapipe(sys.stderr) and '_LAUNCHED_BY_PLATFORM' in os.environ:
            handler.setFormatter(JsonFormatter())
        else:
            fmt = '%(asctime)s %(name)s %(levelname)s: %(message)s'
            #fmt = '%(asctime)s %(name)s %(levelname)s: [%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s'
            handler.setFormatter(logging.Formatter(fmt))

        root.addHandler(handler)
    root.setLevel(level)

def format_timestamp(time_stamp):
    """Create a consistent datetime string representation based on ISO 8601 format.
    
    YYYY-MM-DDTHH:MM:SS.mmmmmm for unaware datetime objects.
    YYYY-MM-DDTHH:MM:SS.mmmmmm+HH:MM for aware datetime objects
    
    :param time_stamp: value to convert
    :type time_stamp: datetime
    :returns: datetime in string format
    :rtype: str
    """
    
    time_str = time_stamp.strftime("%Y-%m-%dT%H:%M:%S.%f")
    
    if time_stamp.tzinfo is not None:
        sign = '+'
        td = time_stamp.tzinfo.utcoffset(time_stamp)
        if td.days < 0:
            sign = '-'
            td = -td
            
        seconds = td.seconds
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        time_str += "{sign}{HH:02}:{MM:02}".format(sign=sign, HH=hours, MM=minutes)
    
    return time_str

def parse_timestamp_string(time_stamp_str):
    """Create a datetime object from the supplied date/time string.
    Uses dateutil.parse with no extra parameters.
    
    :param time_stamp: value to convert
    :type time_stamp: str
    :returns: datetime object
    :rtype: datetime
    """
    return parse(time_stamp_str)

def get_aware_utc_now():
    """Create a timezone aware UTC datetime object from the system time.
    
    :returns: an aware UTC datetime object
    :rtype: datetime
    """
    utcnow = datetime.utcnow()
    utcnow = pytz.UTC.localize(utcnow)
    return utcnow
    
def process_timestamp(timestamp_string, topic=''):
    if timestamp_string is None:
        _log.error("message for {topic} missing timetamp".format(topic=topic))
        return
    
    try:
        timestamp = parse(timestamp_string)
    except (ValueError, TypeError) as e:
        _log.error("message for {topic} bad timetamp string: {ts_string}".format(topic=topic,
                                                                                 ts_string=timestamp_string))
        return

    if timestamp.tzinfo is None:
        timestamp.replace(tzinfo=pytz.UTC)
        original_tz = None
    else:
        original_tz = timestamp.tzinfo
        timestamp = timestamp.astimezone(pytz.UTC)
    return timestamp, original_tz

def watch_file(fullpath, callback):
    '''Run callback method whenever the file changes'''
    dirname, filename = os.path.split(fullpath)
    with inotify() as inot:
        inot.add_watch(dirname, IN_MODIFY)
        for event in inot:
            if event.name == filename and event.mask & IN_MODIFY:
                callback()

def create_file_if_missing(path, permission=0o660, contents=None):
    try:
        fil = open(path)
    except IOError as exc:
        if exc.errno != errno.ENOENT:
            raise
        _log.debug('missing file %s', path)
        _log.info('creating file %s', path)
        fd = os.open(path, os.O_CREAT|os.O_WRONLY, permission)
        try:
            if contents:
                os.write(fd, contents)
        finally:
            os.close(fd)
            
def fix_sqlite3_datetime(sql=None):
    """Primarily for fixing the base historian cache on certain versions of python. 
    
    Registers a new datetime converter to that uses dateutil parse. This should 
    better resolve #216, #174, and #91 without the goofy workarounds that change data.
    
    Optional sql argument is for testing only.
    """
    if sql is None:
        import sqlite3 as sql
    sql.register_converter("timestamp", parse)

# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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

"""VOLTTRON platform™ agent helper classes/functions."""

import argparse
import calendar
import errno
import logging
import sys
import syslog
import traceback
from datetime import datetime, tzinfo, timedelta

import gevent
import os
import pytz
import re
import stat
import time
import yaml
from volttron.platform import get_home, get_address
from dateutil.parser import parse
from dateutil.tz import tzutc, tzoffset
from tzlocal import get_localzone
from volttron.platform.agent import json as jsonapi

try:
    from ..lib.inotify.green import inotify, IN_MODIFY
except AttributeError:
    # inotify library is not available on OS X/MacOS.
    # @TODO Integrate with the OS X FS Events API
    inotify = None
    IN_MODIFY = None

__all__ = ['load_config', 'run_agent', 'start_agent_thread',
           'is_valid_identity']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2016, Battelle Memorial Institute'
__license__ = 'FreeBSD'

_comment_re = re.compile(
    r'((["\'])(?:\\?.)*?\2)|(/\*.*?\*/)|((?:#|//).*?(?=\n|$))',
    re.MULTILINE | re.DOTALL)

_log = logging.getLogger(__name__)

# The following are the only allowable characters for identities.
_VALID_IDENTITY_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def is_valid_identity(identity_to_check):
    """ Checks the passed identity to see if it contains invalid characters

    A None value for identity_to_check will return False

    @:param: string: The vip_identity to check for validity
    @:return: boolean: True if values are in the set of valid characters.
    """

    if identity_to_check is None:
        return False

    return _VALID_IDENTITY_RE.match(identity_to_check)


def normalize_identity(pre_identity):
    if is_valid_identity(pre_identity):
        return pre_identity

    if pre_identity is None:
        raise ValueError("Identity cannot be none.")

    norm = ""
    for s in pre_identity:
        if _VALID_IDENTITY_RE.match(s):
            norm += s
        else:
            norm += '_'

    return norm


def _repl(match):
    """Replace the matched group with an appropriate string."""
    # If the first group matched, a quoted string was matched and should
    # be returned unchanged.  Otherwise a comment was matched and the
    # empty string should be returned.
    return match.group(1) or ''


def strip_comments(string):
    """Return string with all comments stripped.

    Both JavaScript-style comments (//... and /*...*/) and hash (#...)
    comments are removed.
    """
    return _comment_re.sub(_repl, string)


def load_config(config_path):
    """Load a JSON-encoded configuration file."""
    if config_path is None:
        _log.info("AGENT_CONFIG does not exist in environment. load_config returning empty configuration.")
        return {}

    if not os.path.exists(config_path):
        _log.info("Config file specified by AGENT_CONFIG does not exist. load_config returning empty configuration.")
        return {}

    # First attempt parsing the file with a yaml parser (allows comments natively)
    # Then if that fails we fallback to our modified json parser.
    try:
        with open(config_path) as f:
            return yaml.safe_load(f.read())
    except yaml.scanner.ScannerError as e:
        try:
            with open(config_path) as f:
                return parse_json_config(f.read())
        except StandardError as e:
            _log.error("Problem parsing agent configuration")
            raise

def update_kwargs_with_config(kwargs, config):
    """
    Loads the user defined configurations into kwargs.
     
      1. Converts any dash/hyphen in config variables into underscores
      2. Checks for configured "identity" value. Prints a deprecation 
      warning and uses it. 
      3. Checks for configured "agentid" value. Prints a deprecation warning 
      and ignores it
      
    :param kwargs: kwargs to be updated
    :param config: dictionary of user/agent configuration
    """

    if config.get('identity') is not None:
        _log.warning("DEPRECATION WARNING: Setting a historian's VIP IDENTITY"
                     " from its configuration file will no longer be supported"
                     " after VOLTTRON 4.0")
        _log.warning(
            "DEPRECATION WARNING: Using the identity configuration setting "
            "will override the value provided by the platform. This new value "
            "will not be reported correctly by 'volttron-ctl status'")
        _log.warning("DEPRECATION WARNING: Please remove 'identity' from your "
                     "configuration file and use the new method provided by "
                     "the platform to set an agent's identity. See "
                     "scripts/core/make-mongo-historian.sh for an example of "
                     "how this is done.")

    if config.get('agentid') is not None:
        _log.warning("WARNING: Agent id cannot be configured. It is a unique "
                     "id assigned by VOLTTRON platform. Ignoring configured "
                     "agentid")
        config.pop('agentid')

    for k, v in config.items():
        kwargs[k.replace("-","_")] = v


def parse_json_config(config_str):
    """Parse a JSON-encoded configuration file."""
    return jsonapi.loads(strip_comments(config_str))


def run_agent(cls, subscribe_address=None, publish_address=None,
              config_path=None, **kwargs):
    """Instantiate an agent and run it in the current thread.

    Attempts to get keyword parameters from the environment if they
    are not set.
    """
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
    """Instantiate an agent class and run it in a new daemon thread.

    Returns the thread object.
    """
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
    """Default main entry point implementation for legacy agents.

    description and parser_class are depricated. Please avoid using them.
    """
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


def vip_main(agent_class, identity=None, version='0.1', **kwargs):
    """Default main entry point implementation for VIP agents."""
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

        config = os.environ.get('AGENT_CONFIG')
        identity = os.environ.get('AGENT_VIP_IDENTITY', identity)
        if identity is not None:
            if not is_valid_identity(identity):
                _log.warn('Deprecation warining')
                _log.warn(
                    'All characters in {identity} are not in the valid set.'
                    .format(idenity=identity))

        address = get_address()
        agent_uuid = os.environ.get('AGENT_UUID')
        volttron_home = get_home()

        agent = agent_class(config_path=config, identity=identity,
                            address=address, agent_uuid=agent_uuid,
                            volttron_home=volttron_home,
                            version=version, **kwargs)
        
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
                  logging.CRITICAL: syslog.LOG_CRIT}

    def format(self, record):
        level = self._level_map.get(record.levelno, syslog.LOG_INFO)
        return '<{}>'.format(level) + super(SyslogFormatter, self).format(
            record)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        dct = record.__dict__.copy()
        dct["msg"] = record.getMessage()
        dct.pop('args')
        exc_info = dct.pop('exc_info', None)
        if exc_info:
            dct['exc_text'] = ''.join(traceback.format_exception(*exc_info))
        return jsonapi.dumps(dct)


class AgentFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None):
        if fmt is None:
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
            handler.setFormatter(logging.Formatter(fmt))

        root.addHandler(handler)
    root.setLevel(level)


def format_timestamp(time_stamp):
    """Create a consistent datetime string representation based on
    ISO 8601 format.
    
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
        time_str += "{sign}{HH:02}:{MM:02}".format(sign=sign,
                                                   HH=hours,
                                                   MM=minutes)

    return time_str


def parse_timestamp_string(time_stamp_str):
    """
    Create a datetime object from the supplied date/time string.
    Uses dateutil.parse with no extra parameters.

    For performance reasons we try
    YYYY-MM-DDTHH:MM:SS.mmmmmm
    or
    YYYY-MM-DDTHH:MM:SS.mmmmmm+HH:MM
    based on the string length before falling back to dateutil.parse.

    @param time_stamp_str:
    @return: value to convert
    """

    if len(time_stamp_str) == 26:
        try:
            return datetime.strptime(time_stamp_str, "%Y-%m-%dT%H:%M:%S.%f")
        except ValueError:
            pass

    elif len(time_stamp_str) == 32:
        try:
            base_time_stamp_str = time_stamp_str[:26]
            time_zone_str = time_stamp_str[26:]
            time_stamp = datetime.strptime(base_time_stamp_str, "%Y-%m-%dT%H:%M:%S.%f")
            # Handle most common case.
            if time_zone_str == "+00:00":
                return time_stamp.replace(tzinfo=pytz.UTC)

            hours_offset = int(time_zone_str[1:3])
            minutes_offset = int(time_zone_str[4:6])

            seconds_offset = hours_offset * 3600 + minutes_offset * 60
            if time_zone_str[0] == "-":
                seconds_offset = -seconds_offset

            return time_stamp.replace(tzinfo=tzoffset("", seconds_offset))

        except ValueError:
            pass

    return parse(time_stamp_str)


def get_aware_utc_now():
    """Create a timezone aware UTC datetime object from the system time.
    
    :returns: an aware UTC datetime object
    :rtype: datetime
    """
    utcnow = datetime.utcnow()
    utcnow = pytz.UTC.localize(utcnow)
    return utcnow


def get_utc_seconds_from_epoch(timestamp=None):
    """
    convert a given time stamp to seconds from epoch based on utc time. If
    given time is naive datetime it is considered be local to where this
    code is running.
    @param timestamp: datetime object
    @return: seconds from epoch
    """

    if timestamp is None:
        timestamp = datetime.now(tz=tzutc())

    if timestamp.tzinfo is None:
        local_tz = get_localzone()
        # Do not use datetime.replace(tzinfo=local_tz) instead use localize()
        timestamp = local_tz.localize(timestamp)

    # utctimetuple can be called on aware timestamps and it will
    # convert to UTC first.
    seconds_from_epoch = calendar.timegm(timestamp.utctimetuple())
    # timetuple loses microsecond accuracy so we have to put it back.
    seconds_from_epoch += timestamp.microsecond / 1000000.0
    return seconds_from_epoch


def process_timestamp(timestamp_string, topic=''):
    """
    Convert timestamp string timezone aware utc timestamp
    @param timestamp_string: datetime string to parse
    @param topic: topic to which parse errors are published
    @return: UTC datetime object and the original timezone of input datetime
    """
    if timestamp_string is None:
        _log.error("message for {topic} missing timetamp".format(topic=topic))
        return

    try:
        timestamp = parse_timestamp_string(timestamp_string)
    except (ValueError, TypeError):
        _log.error("message for {topic} bad timetamp string: {ts_string}"
                   .format(topic=topic, ts_string=timestamp_string))
        return

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=pytz.UTC)
        original_tz = None
    else:
        original_tz = timestamp.tzinfo
        timestamp = timestamp.astimezone(pytz.UTC)
    return timestamp, original_tz


def watch_file(fullpath, callback):
    """Run callback method whenever the file changes

        Not available on OS X/MacOS.
    """
    dirname, filename = os.path.split(fullpath)
    if inotify is None:
        _log.warning("Runtime changes to: %s not supported on this platform.", fullpath)
    else:
        with inotify() as inot:
            inot.add_watch(dirname, IN_MODIFY)
            for event in inot:
                if event.name == filename and event.mask & IN_MODIFY:
                    callback()


def watch_file_with_fullpath(fullpath, callback):
    """Run callback method whenever the file changes

        Not available on OS X/MacOS.
    """
    dirname, filename = os.path.split(fullpath)
    if inotify is None:
        _log.warning("Runtime changes to: %s not supported on this platform.", fullpath)
    else:
        with inotify() as inot:
            inot.add_watch(dirname, IN_MODIFY)
            for event in inot:
                if event.name == filename and event.mask & IN_MODIFY:
                    callback(fullpath)


def create_file_if_missing(path, permission=0o660, contents=None):
    dirname = os.path.dirname(path)
    if dirname and not os.path.exists(dirname):
        try:
            os.makedirs(dirname)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
    try:
        open(path)
    except IOError as exc:
        if exc.errno != errno.ENOENT:
            raise
        _log.debug('missing file %s', path)
        _log.info('creating file %s', path)
        fd = os.open(path, os.O_CREAT | os.O_WRONLY, permission)
        try:
            if contents:
                os.write(fd, contents)
        finally:
            os.close(fd)


def fix_sqlite3_datetime(sql=None):
    """Primarily for fixing the base historian cache on certain versions
    of python.
    
    Registers a new datetime converter to that uses dateutil parse. This
    should
    better resolve #216, #174, and #91 without the goofy workarounds that
    change data.
    
    Optional sql argument is for testing only.
    """
    if sql is None:
        import sqlite3 as sql
    sql.register_adapter(datetime, format_timestamp)
    sql.register_converter("timestamp", parse_timestamp_string)

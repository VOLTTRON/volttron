# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2013, Battelle Memorial Institute
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

# pylint: disable=W0142,W0403
#}}}

'''VOLTTRON platform™ agent helper classes/functions.'''

import argparse
import logging
import os
import re
import stat
import sys
import syslog
import traceback

from zmq.utils import jsonapi


__all__ = ['load_config', 'run_agent', 'start_agent_thread', 'ArgumentParser']

__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2013, Battelle Memorial Institute'
__license__ = 'FreeBSD'


_comment_re = re.compile(
        r'((["\'])(?:\\?.)*?\2)|(/\*.*?\*/)|((?:#|//).*?(?=\n|$))',
        re.MULTILINE | re.DOTALL)


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
    '''Default main entry point implementation.
    
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
        if sub_addr.startswith('ipc://'):
            if not os.path.exists(sub_addr[6:]):
                sys.stderr.write('warning: subscription socket does not '
                                 'exist: {}\n'.format(sub_addr[6:]))
        if pub_addr.startswith('ipc://'):
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
        return super(AgentFormatter, self).format(record)


def setup_logging(level=logging.DEBUG):
    handler = logging.StreamHandler()
    if isapipe(sys.stderr):
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
                '%(asctime)s %(name)s %(levelname)s: %(message)s'))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level)


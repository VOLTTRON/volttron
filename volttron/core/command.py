# 
# Copyright (c) 2013, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met: 
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer. 
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution. 
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies, 
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an 
# agency of the United States Government.  Neither the United States 
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization 
# that has cooperated in the development of these materials, makes 
# any warranty, express or implied, or assumes any legal liability 
# or responsibility for the accuracy, completeness, or usefulness or 
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or 
# service by trade name, trademark, manufacturer, or otherwise does 
# not necessarily constitute or imply its endorsement, recommendation, 
# r favoring by the United States Government or any agency thereof, 
# or Battelle Memorial Institute. The views and opinions of authors 
# expressed herein do not necessarily state or reflect those of the 
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
#


import argparse
import re
import sys


__all__ = ['CommandParser']


class CountdownAction(argparse._CountAction):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, getattr(namespace, self.dest, 0) - 1)


class ConfigSetAction(argparse._StoreAction):
    _confsetre = re.compile(r'^\s*(\w+(?:\.\w+)+)\s*=\s*(\S.*?)\s*$')
    def __call__(self, parser, namespace, values, option_string=None):
        value = getattr(namespace, self.dest, None)
        if value is None:
            value = []
            setattr(namespace, self.dest, value)
        if isinstance(values, basestring):
            values = [values]
        for string in values:
            match = ConfigSetAction._confsetre.match(string)
            if match is None:
                raise argparse.ArgumentTypeError(
                        'not a valid config string: {!r} '
                        "(use 'section.name=value')".format(string))
            names, setting = match.groups()
            value.append((names.split('.'), setting))


class CommandParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        self.aliases = kwargs.pop('aliases', None)
        self.help = kwargs.pop('help', '')
        handler = kwargs.pop('handler', None)
        add_help = kwargs.pop('add_help', True)
        help_action = kwargs.pop('help_action', 'help')
        version = kwargs.pop('version', None)
        globals = kwargs.pop('globals', None)
        kwargs['add_help'] = False
        super(CommandParser, self).__init__(*args, **kwargs)
        if handler:
            self.set_defaults(handler=handler)
        self._globals = self.add_argument_group('global options', argparse.SUPPRESS)
        #self._optionals.description = argparse.SUPPRESS
        self.add_global_arguments(self._globals)
        if add_help:
            self._globals.add_argument('-h', '--help', action=help_action,
                    help='display this help message and exit')
        if version:
            self._globals.add_argument('--version', action='version', version=version)

    def format_help(self):
        formatter = self._get_formatter()
        # usage
        actions = [act for act in self._actions
                   if act.container is not self._globals]
        formatter.add_usage(self.usage, actions,
                            self._mutually_exclusive_groups)
        # aliases
        if self.aliases:
            formatter.add_text('aliases: {}\n'.format(', '.join(self.aliases)))
        # description
        if self.description is not argparse.SUPPRESS:
            formatter.add_text(self.description)
        # positionals, optionals and user-defined groups
        for action_group in self._action_groups:
            if action_group is self._globals:
                continue
            formatter.start_section(action_group.title)
            if action_group.description is not argparse.SUPPRESS:
                formatter.add_text(action_group.description)
            formatter.add_arguments(action_group._group_actions)
            formatter.end_section()
        # epilog
        if self.epilog:
            formatter.add_text(self.epilog)
        # determine help from format above
        return formatter.format_help()

    def format_usage(self):
        formatter = self._get_formatter()
        actions = [act for act in self._actions
                   if act.container is not self._globals]
        formatter.add_usage(self.usage, actions,
                            self._mutually_exclusive_groups)
        return formatter.format_help()
    
    def add_global_arguments(self, group):
        group.add_argument('-c', '--config', action='store', default=None,
                          help='specify configuration file')
        group.add_argument('-s', '--set', action=ConfigSetAction, default=[],
                           dest='extra_config', metavar='SECTION.NAME=VALUE',
                           help='specify additional configuration')
        group.add_argument('-q', '--quiet', action=CountdownAction,
                            dest='verboseness', default=0,
                            help='decrease verboseness of output')
        group.add_argument('-v', '--verbose', action='count', dest='verboseness',
                            help='increase verboseness of output')

    def format_global_arguments(self):
        formatter = self._get_formatter()
        action_group = self._globals
        formatter.start_section(action_group.title)
        if action_group.description is not argparse.SUPPRESS:
            formatter.add_text(action_group.description)
        formatter.add_arguments(action_group._group_actions)
        formatter.end_section()
        return formatter.format_help()

    def print_global_arguments(self, file=None):
        if file is None:
            file = sys.stdout
        self._print_message('\n', file)
        self._print_message(self.format_global_arguments(), file)

    # Override sub-command parsing to provide shortest match matching
    def _get_value(self, action, arg_string):
        result = super(CommandParser, self)._get_value(action, arg_string)
        if (action.nargs == argparse.PARSER and
                action.choices is not None and result not in action.choices):
            matches = [name for name in action.choices if name.startswith(result)]
            if not matches:
                return result
            if len(matches) == 1:
                return matches[0]
            msg = 'ambiguous choice: {!r} (choose from {})'.format(
                    result, ', '.join(matches))
            raise argparse.ArgumentError(action, msg)
        return result


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

'''Advanced argument parser.

Fully compatible with argparse, and can be used as a drop-in
replacement, with the added ability add options from configuration files
and environment variables. The default order of precedense is
command-line > environment > config file > defaults.  The only change
which can be made to this order is to instruct the configuration file
action to add options inline rather than at the beginning, causing
configuration options to be parsed after environment variables and in
the order encountered.
'''

import argparse as _argparse
import os as _os
import re as _re
import shlex as _shlex
import sys as _sys


class TrackingString(str):
    '''String subclass that allows attaching source information.'''
    def __new__(cls, *args, **kwargs):
        source = kwargs.pop('source', None)
        obj = str.__new__(cls, *args, **kwargs)
        obj.source = source
        return obj


class AddConstAction(_argparse.Action):
    '''Add a constant value to the option.'''
    def __init__(self, option_strings, dest, const=1, type=int,
                 default=None, required=False, help=None):
        super(AddConstAction, self).__init__(
                option_strings=option_strings, dest=dest, nargs=0, type=type,
                const=const, default=default, required=required, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        value = getattr(namespace, self.dest, None) or 0
        setattr(namespace, self.dest, value + self.const)


class ListAction(_argparse.Action):
    '''Action to store space or comma separated lists.'''
    def split(self, value):
        buf = []
        esc = False
        for c in value:
            if esc:
                buf.append(c)
                esc = False
            elif c == '\\':
                esc = True
            elif c.isspace() or c == ',':
                if buf:
                    yield ''.join(buf)
                    del buf[:]
            else:
                buf.append(c)
        if buf:
            yield ''.join(buf)

    def __call__(self, parser, namespace, value, option_string=None):
        if value and value[:1] in '!-+':
            values = set(getattr(namespace, self.dest, []))
            list_values = set(self.split(value[1:]))
            if value[:1] == '+':
                values |= list_values
            else:
                values -= list_values
        elif not value:
            values = None
        else:
            values = set(self.split(value))
        setattr(namespace, self.dest, list(values))


class ConfigFileAction(_argparse.Action):
    '''Read a configuration file and add it to the arguments to be parsed.

    The file should contain one "long option" per line, with or without
    the leading option characters (usually --), and otherwise entered as
    on the command-line with shell-style quoting. Lines beginning with
    a hash (#) or semicolon (;) and empty lines are ignored. Hashes (#)
    may also be used to comment option lines, excluding everything from
    the comment character to the end of the line. Key-value options may
    be separated by =, : or whitespace.

    By default, INI-style section markers are ignored. If, however, a
    program wants only to use settings in certain sections, it may pass
    a list of sections to allow. All other sections will be ignored.
    Section names are case-sensitive. The special None section will
    include global values which appear in the file before and section is
    declared.

    Options which set their config flag to False will not be allowed in
    configuration files. A default value can be set on the parser with
    the allow_in_config option.

    If ignore_unknown is True, lines containing an unknown option key
    will be ignored. Otherwise, an error will be issued (default
    behavior).  Options read from the configuration file will normally
    be added before those for environment variables and other
    command-line arguments and in the order encountered to maintain the
    normal order of precedence.  If inline is True, the configuration
    options will be inserted in place of the configuration option and
    will be processed after environment variables.
    '''

    def __init__(self, option_strings, dest,
                 required=False, help=None, metavar=None, **kwargs):
        ignore_unknown = kwargs.pop('ignore_unknown', None)
        inline = kwargs.pop('inline', False)
        sections = kwargs.pop('sections', None)
        super(ConfigFileAction, self).__init__(
            option_strings=option_strings, dest=_argparse.SUPPRESS,
                required=required, help=help, metavar=metavar)
        self.ignore_unknown = ignore_unknown
        self.inline = inline
        self.sections = sections
        self.preprocess = True

    def __call__(self, parser, namespace, path, option_string=None, seen_files=None):
        # Get default for including argument in config.
        allow_in_config = getattr(parser, 'allow_in_config', True)
        if seen_files is None:
            seen_files = set()
        arg_strings = []
        try:
            with open(path) as file:
                stat = _os.fstat(file.fileno())
                file_id = stat.st_dev, stat.st_ino
                # Detect config file loops
                if file_id in seen_files:
                    # XXX: Should a warning be issued?
                    return [], []
                seen_files.add(file_id)
                for section, key, args, lineno in self.itersettings(parser, file):
                    if self.sections is not None and section not in self.sections:
                        continue
                    source = ('config', (path, lineno, key))
                    opt = TrackingString((key if key.startswith('--')
                                         else ('--' + key)), source=source)
                    try:
                        action = parser._option_string_actions[opt]
                    except KeyError:
                        if self.ignore_unknown:
                            continue
                        parser.error('{} (line {}): unknown option: {}'.format(
                                path, lineno, key))
                    if not getattr(action, 'config', allow_in_config):
                        parser.error('{} (line {}): option not allowed: {}'.format(
                                path, lineno, key))
                    if isinstance(action, ConfigFileAction):
                        if args is None or len(args) != 1:
                            parser.error(
                                '{} (line {}): option expects one argument: {}'.format(
                                    path, lineno, key))
                        for arg_list in self(
                                parser, namespace, args[0], opt, seen_files=seen_files):
                            arg_strings.extend(arg_list)
                    else:
                        if action.nargs == 0 and args:
                            if len(args) > 1:
                                parser.error('{} (line {}): option expects no '
                                             'more than one argument: {}'.format(
                                                path, lineno, key))
                            opt = parser.get_switch(action, args[0], opt)
                            arg_strings.append(TrackingString(opt, source=source))
                        else:
                            arg_strings.append(opt)
                            if args:
                                arg_strings.extend(args)
        except IOError as e:
            parser.error('{}: {}'.format(path, e))
        return ([], arg_strings) if self.inline else (arg_strings, [])

    def itersettings(self, parser, conffile):
        section_re = _re.compile(r'^\s*\[\s*((?:\\.|[^\]])*?)\s*\](.*)$')
        comment_re = _re.compile(r'^\s*(?:[#;].*)?$')
        setting_re = _re.compile(r'^(\S+?)(?:(?:\s*[:=]\s*|\s+)(.*))?$')
        section = None
        for lineno, line in enumerate(conffile):
            if not line:
                break
            line = line.strip()
            if not line or comment_re.match(line):
                continue
            match = section_re.match(line)
            if match:
                section, rest = match.groups()
                if not comment_re.match(rest):
                    err = 'invalid syntax after section: {!r}'.format(rest)
                    parser.error('{}: {} (line {})'.format(conffile.name, err, lineno))
                # Remove backslash escapes
                section = _re.sub(r'\\(.)', r'\1', section)
                continue
            key, value = setting_re.match(line).groups()
            if value is not None:
                try:
                    value = _shlex.split(value, True, True)
                except ValueError as e:
                    parser.error('{}: {} (line {})'.format(conffile.name, e, lineno))
            yield section, key, value, lineno


def CaseInsensitiveConfigFileAction(ConfigFileAction):
    def itersettings(self, parser, conffile):
        itersettings = super(CaseInsensitiveConfigFileAction, self).itersettings
        for section, key, value, lineno in itersettings(parser, conffile):
            if section is not None:
                section = section.lower()
            yield section, key, value, lineno


def env_var_formatter(formatter_class=_argparse.HelpFormatter):
    '''Decorator to automatically add env_var documentation to help.'''
    class EnvHelpFormatter(formatter_class):
        def _get_help_string(self, action):
            # pylint: disable=super-on-old-class
            help = super(EnvHelpFormatter, self)._get_help_string(action)
            if '%(env_var)' not in help:
                env_var = getattr(action, 'env_var', None)
                if env_var is not None:
                    help += ' (env var: %(env_var)s)'
            return help
    return EnvHelpFormatter


class ArgumentParser(_argparse.ArgumentParser):
    _false_re = _re.compile(r'^\s*(f(?:alse)?|n(?:o)?|0)?\s*$', _re.I)

    def __init__(self, *args, **kwargs):
        allow_in_config = kwargs.pop('allow_in_config', True)
        super(ArgumentParser, self).__init__(*args, **kwargs)
        self.allow_in_config = allow_in_config
        self.register('action', 'add_const', AddConstAction)
        self.register('action', 'store_list', ListAction)
        self.register('action', 'parse_config', ConfigFileAction)

    def _parse_known_args(self, arg_strings, namespace):
        # replace arg strings that are file references
        if self.fromfile_prefix_chars is not None:
            arg_strings = self._read_args_from_files(arg_strings)
        arg_strings = self._preprocess_args(arg_strings, namespace)
        return super(ArgumentParser, self)._parse_known_args(arg_strings, namespace)

    def _preprocess_args(self, arg_strings, namespace):
        '''Pre-process arguments.

        May be overridden to change the order options are applied.
        '''
        config_args, cli_args = self._parse_early_args(arg_strings, namespace)
        env_args = self._parse_environment(namespace)
        return config_args + env_args + cli_args

    def _parse_early_args(self, arg_strings, namespace):
        '''Pre-parse args to expand preprocessed options.

        This may include reading options from configuration files.
        '''
        config_args = []
        cli_args = []
        if not arg_strings:
            return config_args, cli_args
        if self._subparsers is not None:
            subcommands = {name for action in self._subparsers._group_actions
                           if hasattr(action, '_name_parser_map')
                           for name in action._name_parser_map}
        else:
            subcommands = set()
        args_enumerator = enumerate(arg_strings)
        args_iterator = (arg for i, arg in args_enumerator)
        def _take(n):
            if n > 0:
                for arg in args_iterator:
                    yield arg
                    n -= 1
                    if not n:
                        break
        take = lambda n: list(_take(n))
        for i, arg_string in args_enumerator:
            if arg_string == '--' or arg_string in subcommands:
                # All remaining arguments are considered positional
                cli_args.append(arg_string)
                break
            option_tuple = self._parse_optional(arg_string)
            if option_tuple is None or option_tuple[0] is None:
                # This argument is positional; skip further processing
                cli_args.append(arg_string)
                continue
            # Some kind of option was encountered, so deal with it
            action, option_string, explicit_arg = option_tuple
            if explicit_arg is not None:
                args = [explicit_arg]
            elif action.nargs in [_argparse.REMAINDER, _argparse.PARSER]:
                args = list(args_iterator)
            elif action.nargs is None:
                args = take(1)
            elif isinstance(action.nargs, int):
                args = take(action.nargs)
            else:
                # Consume arguments until another option is found
                args = take(1) if action.nargs is _argparse.ONE_OR_MORE else []
                n = 0
                for n, arg in enumerate(arg_strings[i+1:]):
                    if arg == '--' or arg in subcommands:
                        break
                    option_tuple = self._parse_optional(arg)
                    if option_tuple is not None and option_tuple[0] is not None:
                        break
                args.extend(take(n))
            args_tuple = self.preprocess_option(
                    action, namespace, args, option_string)
            if args_tuple is not None:
                extra_config, extra_cli = args_tuple
                config_args.extend(extra_config)
                cli_args.extend(extra_cli)
            elif explicit_arg is None:
                cli_args.append(arg_string)
                cli_args.extend(args)
            else:
                cli_args.append(arg_string)
        cli_args.extend(args_iterator)
        return config_args, cli_args

    def _parse_environment(self, namespace):
        '''Create arguments for actions with associated environment vars.'''
        arg_strings = []
        for action in self._actions:
            # Ignore positionals
            if not action.option_strings:
                continue
            try:
                value = _os.environ[action.env_var]
            except (AttributeError, KeyError):
                continue
            for opt in action.option_strings:
                if opt.startswith('--'):
                    break
            source = ('environment', action.env_var)
            if action.nargs == 0:
                opt = TrackingString(self.get_switch(action, value, opt),
                                    source=source)
                arg_strings.append(opt)
            else:
                opt = TrackingString(opt, source=source)
                arg_strings.extend([opt, value])
        return arg_strings

    def preprocess_option(self, action, namespace, arg_strings, option_string):
        '''Pre-process an action.

        If an action has a preprocess attribute which evaluates to True,
        then execute the action now. This type of action is expected to
        return None if it is to remain in the argument list unchanged.
        Otherwise, it should return two lists: the first will be
        appended to the configuration arguments and the second will
        replace the processed arguments.
        '''
        if not getattr(action, 'preprocess', False):
            return
        values = self._get_values(action, arg_strings)
        if action.nargs in [None, _argparse.OPTIONAL] and len(arg_strings) != 1:
            return
        return action(self, namespace, values, option_string)

    def get_switch(self, action, value, option_string):
        '''Convert argument-less options when they have an argument.

        Useful for allowing options in a configuration file and
        environment variables to be set or unset based on an argument
        which looks like a boolean. To be invert-able, the action must
        set its inverse attribute to an option that will invert the
        meaning.
        '''
        if self._false_re.match(value) is None:
            return option_string
        inverse = getattr(action, 'inverse', None)
        if not inverse:
            self.error('option cannot be inverted: {}'.format(option_string))
        return inverse

    def add_help_argument(self, *args, **kwargs):
        if not args:
            prefix_chars = self.prefix_chars
            default_prefix = '-' if '-' in prefix_chars else prefix_chars[0]
            args = [default_prefix + 'h', default_prefix*2 + 'help']
        kwargs.setdefault('action', 'help')
        kwargs.setdefault('default', _argparse.SUPPRESS)
        kwargs.setdefault('help', _argparse._('show this help message and exit'))
        self.add_argument(*args, **kwargs)

    def add_version_argument(self, *args, **kwargs):
        if not args:
            prefix_chars = self.prefix_chars
            default_prefix = '-' if '-' in prefix_chars else prefix_chars[0]
            args = [default_prefix*2 + 'version']
        kwargs.setdefault('action', 'version')
        kwargs.setdefault('default', _argparse.SUPPRESS)
        kwargs.setdefault('help',
                          _argparse._("show program's version number and exit"))
        self.add_argument(*args, **kwargs)


class TrackingArgumentParser(ArgumentParser):
    '''Wrap up calls to actions to pre- and post-handlers.

    This class is useful as a base class for debugging parsers.
    '''
    def _parse_known_args(self, arg_strings, namespace):
        self._setup_tracking()
        return super(TrackingArgumentParser, self)._parse_known_args(arg_strings, namespace)

    def _setup_tracking(self):
        def __call__(action, parser, namespace, values, option_string=None, **kwargs):
            source = getattr(option_string, 'source',
                             ('command-line', option_string))
            self.pre_action(action, parser, namespace, values, option_string, source)
            result = super(action.__class__, action).__call__(
                    parser, namespace, values, option_string, **kwargs)
            self.post_action(action, parser, namespace, values, option_string, source)
            return result
        for action in self._actions:
            cls = action.__class__
            if getattr(cls, '_trackable', False):
                continue
            action.__class__ = type(cls.__name__, (cls,),
                                    {'__call__': __call__, '_trackable': True})

    def pre_action(self, action, parser, namespace, values, option_string, source):
        pass

    def post_action(self, action, parser, namespace, values, option_string, source):
        pass


class DebugArgumentParser(TrackingArgumentParser):
    '''Write options to stderr as they are added to the namespace.

    This includes the source of the change. It does not include defaults.
    '''
    def post_action(self, action, parser, namespace, values, option_string, source):
        if action.dest is _argparse.SUPPRESS:
            return
        value = getattr(namespace, action.dest, None)
        _sys.stderr.write('{} {} {!r} {!r}\n'.format(
                          option_string, action.dest, source, value))


def _patch_argparse():
    '''Patch argparse to include additional attributes on options.'''
    argparse_add_argument = _argparse._ActionsContainer.add_argument
    def add_argument(*args, **kwargs):
        config = kwargs.pop('config', True)
        env_var = kwargs.pop('env_var', None)
        inverse = kwargs.pop('inverse', None)
        action = argparse_add_argument(*args, **kwargs)
        action.config = config
        action.env_var = env_var
        action.inverse = inverse
        return action
    _argparse._ActionsContainer.add_argument = add_argument
_patch_argparse()


def expandall(string):
    return _os.path.expanduser(_os.path.expandvars(string))

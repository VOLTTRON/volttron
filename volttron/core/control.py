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

#}}}

'''VOLTTRON core control classes/functions.'''


import argparse
import os.path
import sys
import textwrap

from .command import CommandParser


def _format_commands(formatter, commands, verbose=False):
    '''Format the command list using the given formatter'''
    # pylint: disable=W0212
    formatter.start_section('list of commands')
    if verbose:
        indent1 = ' ' * formatter._current_indent
        indent2 = ' ' * (formatter._current_indent + 6)
        def add_command(name, parser):
            aliases = list(parser.aliases or [])
            return '{}{}:\n{}\n'.format(indent1,
                   ', '.join([name] + aliases), formatter._fill_text(
                   parser.help or '', formatter._width, indent2))
    else:
        max_cmd_len = max(len(name) for name, parser in commands)
        indent1 = ' ' * formatter._current_indent
        indent2 = ' ' * (max_cmd_len + formatter._current_indent + 2)
        def add_command(name, parser):
            help_text = '%-*s  %s' % (max_cmd_len, name, parser.help or '')
            return textwrap.fill(help_text, formatter._width,
                    initial_indent=indent1, subsequent_indent=indent2) + '\n'
    for args in commands:
        formatter._add_item(add_command, args)
    formatter.end_section()


def command_help(root_parser, parser, args, file=sys.stdout):
    '''Display help of commands or applicaiton.'''
    # pylint: disable=W0622
    # Help (-h or --help) option given; print command help
    parser.print_help(file)
    if args.verboseness > 0:
        # Verbose help/output requested
        root_parser.print_global_arguments(file)
    else:
        file.write('\nUse `{} {}{}{}-v` to show aliases and global options.'
                   '\n'.format(root_parser.prog, args.command or '',
                               args.command and ' ' or '',
                               args.help and '-h ' or ''))


def match_commands(prefix, commands):
    matching = []
    for name, parser in commands:
        if name == prefix or parser.aliases and name in parser.aliases:
            return [(name, parser)]
        if (name.startswith(prefix) or
                any(n.startswith(prefix) for n in (parser.aliases or []))):
            matching.append((name, parser))
    return matching


def help_help(root_parser, commands, args, explicit=True, file=sys.stdout):
    '''Display help of commands or applicaiton.'''
    # pylint: disable=W0212,W0622
    if args.command and args.command != 'help':
        # One or more commands were given as arguments; select
        # all commands with matching name or alias
        commands = sorted(set([match_commands(prefix, commands)
                              for prefix in args.command]))
    if len(commands) == 1 and args.command:
        # Display command help if only one command matches
        commands[0][1].print_help()
    elif commands:
        # Display short help for all or matching commands
        formatter = root_parser._get_formatter()
        _format_commands(formatter, commands, args.verboseness > 0)
        root_parser.print_help(file)
        file.write('\n')
        file.write(formatter.format_help())
    command = ' '.join(args.command) if args.command else ''
    if args.verboseness > 0:
        # Verbose help/output requested
        root_parser.print_global_arguments(file)
    else:
        file.write('\nUse `{} {}{}{}-v` to show aliases and global options.'
                   '\n'.format(root_parser.prog, explicit and 'help ' or '',
                               command ,command and ' '))


def parse_command(commands, argv=sys.argv, description=None, version=None):
    prog = os.path.basename(argv[0])
    if version:
        version = ' '.join([prog, str(version)])
    # Create the main and help parsers
    root_parser = CommandParser(
            usage='%(prog)s command [options]', description=description,
            help_action='store_true', prog=prog, version=version)
    root_parser.add_argument('command', nargs='?', default=None,
                             help=argparse.SUPPRESS)
    help_parser = CommandParser(usage='help [command]',
                                help='display help about commands')
    help_parser.add_argument('command', nargs='*', help=argparse.SUPPRESS)
    help_parser.set_defaults(handler=lambda e, p, a:
                             help_help(root_parser, commands, a))
    commands.append(('help', help_parser))
    commands.sort()

    # Parse out the first argument as the command to execute
    args, unknown = root_parser.parse_known_args(argv[1:])
    if not args.command:
        help_help(root_parser, commands, args, False)
        sys.exit(0)
    matches = match_commands(args.command, commands)
    if not matches:
        root_parser.error('unknown command: {!r}'.format(args.command))
    if len(matches) > 1:
        root_parser.error('ambiguous command: {!r} (choose from {})'.format(
                args.command, ', '.join(zip(*matches)[0])))
    command, parser = matches[0]
    parser._get_formatter = lambda:parser.formatter_class(
            prog='{} {} [options]'.format(prog, command))
    parser.prog = command
    if args.help:
        command_help(root_parser, parser, args)
        sys.exit(0)

    # Parse the rest of the arguments using the command parser
    args = parser.parse_args(unknown, args)
    if parser is help_parser:
        args.handler(None, parser, args)
        sys.exit(0)
    return parser, args


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


'''Resource Monitor

The resource monitor manages resources assigned to the platform, assigns
resources to agent execution environments, and monitors those resources
for abuse.

There will typically be only a single resource monitor that is
instantiated and then set using set_resource_monitor().  Other modules
may then just import the module and call the module-level functions
without worrying about where to find the monitor instance.
'''


#import ctypes
#from ctypes import c_int, c_ulong
from ast import literal_eval
import os
import re
from volttron.platform import _escape_scan
from volttron.platform.aip import ExecutionEnvironment


__all__ = ['ResourceError', 'ExecutionEnvironment', 'ResourceMonitor']


__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2016, Battelle Memorial Institute'
__license__ = 'Apache 2.0'
__version__ = '0.1'


#_libc = ctypes.CDLL(None, use_errno=True)
#set_pdeathsig = ctypes.CFUNCTYPE(c_int, c_int, c_ulong, use_errno=True)(
#        ('prctl', _libc), ((5, None, 1), (1,)))
#get_pdeathsig = ctypes.CFUNCTYPE(c_int, c_int, c_ulong*1, use_errno=True)(
#        ('prctl', _libc), ((5, None, 2), (2,)))
#
#def _errcheck(result, func, args):
#    if result:
#        errnum = ctypes.get_errno()
#        raise OSError(errnum, os.strerror(errnum))
#    if func is get_pdeathsig:
#        return int(args[1][0])
#set_pdeathsig.errcheck = _errcheck
#get_pdeathsig.errcheck = _errcheck



_key_re = re.compile(r'^\s*([a-zA-Z0-9_]+)=')


def _match_shell_var(line):
    """Return (key, raw_value) as the historical backtracking _var_re did,
    or None. The double- and single-quoted branches close on the shared
    escape scan; the unquoted branch ends at the first '#' that is not
    walled off by an embedded newline, matching what the historical
    lazy [^#]*? plus \\s*(?:#.*)?$ accepted on a single line.
    """
    key_match = _key_re.match(line)
    if not key_match:
        return None
    key = key_match.group(1)
    pos = key_match.end()
    n = len(line)
    # the last newline that is not the line's own final character: nothing
    # past it can still satisfy a $ that only matches end-of-line or just
    # before a truly trailing newline. Computed once, not per candidate.
    bad = line.rfind('\n', 0, n - 1)

    def tail_ok(text, at):
        w = at
        while w < n and text[w].isspace():
            w += 1
        return w == n or (text[w] == '#' and w > bad)

    if pos < n and line[pos] == '"':
        close = _escape_scan.find_close(line, pos + 1, '"', tail_ok)
        if close is not None:
            return key, line[pos:close + 1]
        # falls through to the unquoted alternative, below

    elif pos < n and line[pos] == "'":
        end = line.find("'", pos + 1)
        if end != -1 and tail_ok(line, end + 1):
            return key, line[pos:end + 1]
        # falls through, as above

    hash_pos = line.find('#', pos)
    if hash_pos == -1:
        end = n
    elif hash_pos > bad:
        end = hash_pos
    else:
        return None
    return key, line[pos:end].rstrip()


def _iter_shell_vars(file):
    for key, value in (match for match in
            (_match_shell_var(line) for line in file) if match):
        if value[:1] == "'" == value[-1:]:
            yield key, value[1:-1]
        elif value[:1] == '"' == value[-1:]:
            yield key, literal_eval(value)
        else:
            yield key, value

def lsb_release(path='/etc/lsb-release'):
    try:
        file = open(path)
    except EnvironmentError:
        lsb = {}
    else:
        with file:
            lsb = dict(_iter_shell_vars(file))
    return [
        ('LSB Version', lsb.get('LSB_VERSION', 'n/a')),
        ('Distributor ID', lsb.get('DISTRIB_ID', 'n/a')),
        ('Description', lsb.get('DISTRIB_DESCRIPTION', '(none)')),
        ('Release', lsb.get('DISTRIB_RELEASE', 'n/a')),
        ('Codename', lsb.get('DISTRIB_CODENAME', 'n/a')),
    ]


class ResourceError(Exception):
    '''Exception raised for errors relating to this module.'''
    pass

# TODO is a simple import adequate
# class ExecutionEnvironment:
#     '''Environment reserved for agent execution.
#
#     Deleting ExecutionEnvironment objects should cause the process to
#     end and all resources to be returned to the system.
#     '''
#     def __init__(self):
#         self.process = None
#
#     def execute(self, *args, **kwargs):
#         try:
#             self.process = subprocess.Popen(*args, **kwargs)
#         except OSError as e:
#             if e.filename:
#                 raise
#             raise OSError(*(e.args + (args[0],)))
#
#     def __call__(self, *args, **kwargs):
#         self.execute(*args, **kwargs)


class ResourceMonitor:
    def __init__(self, env, **kwargs):
        pass

    def get_static_resources(self, query_items=None):
        '''Return a dictionary of hard capabilities and static resources.

        query_items is a list of resources the requester is interested
        in; only items in the list will appear in the returned
        dictionary.  If query_items is not passed or is None, all items
        should be returned.

        The returned dictionary contains the requested items that are
        available and their associated values and/or limits.

        Examples of static resources:
            architecture
            kernel version
            distribution (lsb_release)
            installed software
        '''
        kernel, _, release, version, arch = os.uname()
        resources = {
            'kernel.name': kernel,
            'kernel.release': release,
            'kernel.version': version,
            'architecture': arch,
            'os': 'GNU/Linux',
        }
        resources.update(
                [('distribution.' + name.replace(' ', '_').lower(), value)
                 for name, value in lsb_release()])
        if query_items:
            for name in set(resources.keys()).difference(query_items):
                del resources[name]
        return resources

    def check_hard_resources(self, contract):
        '''Test contract against hard resources and return failed terms.

        contract should be a dictionary of terms and conditions that are
        being requested.  If all terms can be met, None is returned.
        Otherwise, a dictionary is returned with the terms that failed
        along with hints on values that would cause the terms to
        succeed, if any.  The contract is tested against the platform's
        hard capabilities and static resources.
        '''
        resources = self.get_static_resources()
        failed = {}
        for name, value in contract.items():
            local_value = resources.get(name)
            if local_value != value:
                failed[name] = local_value
        return failed or None

    # TODO this code not necessary
    # def reserve_soft_resources(self, contract):
    #     '''Test contract against soft resources and reserve resources.
    #
    #     contract should be a dictionary of terms and conditions to test
    #     against the platform's soft capabilities and dynamic resources.
    #
    #     A 2-tuple is returned: (reservation, failed_terms).  If
    #     reservation is None, no resources were reserved and failed_terms
    #     is a dictionary that can be consulted for the terms that must be
    #     modified for a reservation to succeed.  Otherwise, reservation
    #     will be a ExecutionEnvironment object that can later be used to
    #     execute an agent and failed_terms will be None.
    #     '''
    #     execenv = ExecutionEnvironment()
    #     return execenv, None

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
import subprocess


__all__ = ['ResourceError', 'ExecutionEnvironment', 'ResourceMonitor']


__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2013, Battelle Memorial Institute'
__license__ = 'FreeBSD'
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



_var_re = re.compile(
    r'''^\s*([a-zA-Z0-9_]+)=("(?:\\.|[^"])*"|'[^']*'|[^#]*?)\s*(?:#.*)?$''')

def _iter_shell_vars(file):
    for key, value in (match.groups() for match in
            (_var_re.match(line) for line in file) if match):
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


class ExecutionEnvironment(object):
    '''Environment reserved for agent execution.

    Deleting ExecutionEnvironment objects should cause the process to
    end and all resources to be returned to the system.
    '''
    def __init__(self):
        self.process = None

    def execute(self, *args, **kwargs):
        try:
            self.process = subprocess.Popen(*args, **kwargs)
        except OSError as e:
            if e.filename:
                raise
            raise OSError(*(e.args + (args[0],)))

    def __call__(self, *args, **kwargs):
        self.execute(*args, **kwargs)


class ResourceMonitor(object):
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
        for name, value in contract.iteritems():
            local_value = resources.get(name)
            if local_value != value:
                failed[name] = local_value
        return failed or None

    def reserve_soft_resources(self, contract):
        '''Test contract against soft resources and reserve resources.

        contract should be a dictionary of terms and conditions to test
        against the platform's soft capabilities and dynamic resources.

        A 2-tuple is returned: (reservation, failed_terms).  If
        reservation is None, no resources were reserved and failed_terms
        is a dictionary that can be consulted for the terms that must be
        modified for a reservation to succeed.  Otherwise, reservation
        will be a ExecutionEnvironment object that can later be used to
        execute an agent and failed_terms will be None.
        '''
        execenv = ExecutionEnvironment()
        return execenv, None


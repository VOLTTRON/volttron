# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
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

from ast import literal_eval
import functools
import os
import re
import subprocess
import weakref

from . import __version__


__all__ = ['ResourceError', 'ExecutionEnvironment', 'ResourceMonitor',
           'get_static_resources', 'check_hard_resources',
           'reserve_soft_resources', 'set_resource_monitor',
          ]


__author__ = 'Brandon Carpenter <brandon.carpenter@pnnl.gov>'
__copyright__ = 'Copyright (c) 2011 Pacific Northwest National Laboratory.  All rights reserved'


_resource_monitor = None
_cgroups_root = '/sys/fs/cgroup'


def get_bogomips(path='/proc/cpuinfo'):
    bogore = re.compile(r'^bogomips\s*:\s*([0-9.]+)')
    return sum(float(m.group(1)) for m in (bogore.match(l)
                                 for l in open(path)) if m)


def get_total_memory(path='/proc/meminfo'):
    match = re.search(r'^MemTotal\s*:\s*([0-9.]+)', open(path).read())
    return 0 if match is None else int(match.group(1)) * 1024


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


def cgcreate(subsystem, names, root=None):
    if root is None:
        root = _cgroups_root
    path = os.path.join(root, subsystem, *names)
    if (not os.path.exists(path)):
        os.makedirs(path)

def cgremove(subsystem, keep_names, rm_names, root=None):
    if root is None:
        root = _cgroups_root
    path = os.path.join(root, subsystem, *keep_names)
    names = list(rm_names)
    while names:
        os.rmdir(os.path.join(path, *names))
        del names[-1]

def cgget(subsystem, names, root=None):
    if root is None:
        root = _cgroups_root
    path = os.path.join(root, subsystem, *names)
    return open(path, 'r').read()

def cgset(subsystem, names, value, root=None):
    if root is None:
        root = _cgroups_root
    path = os.path.join(root, subsystem, *names)
    open(path, 'w').write(value)

def disable_cgroups():
    def disable(name):
        fn = globals()[name]
        if hasattr(fn, '_original'):
            return
        def wrapper(*args, **kwargs):
            return
        functools.update_wrapper(wrapper, fn)
        wrapper._original = fn
        globals()[name] = wrapper
    for name in ['cgcreate', 'cgremove', 'cgget', 'cgset']:
        disable(name)

if os.environ.get('RESMON_NO_CGROUPS', '').lower() in ['1', 'yes', 'y', 'true']:
    disable_cgroups()

class ResourceError(Exception):
    '''Exception raised for errors relating to this module.'''
    pass


class ExecutionEnvironment(object):
    '''Environment reserved for agent execution.

    Deleting ExecutionEnvironment objects should cause the process to
    end and all resources to be returned to the system.
    '''
    def __init__(self, path, cpu_quota, memory):
        self.process = None
        self.path = path
        self.cpu_quota = cpu_quota
        self.memory = memory

    def execute(self, args, working_dir=os.getcwd(), env=None):
        #Need to start this process in the context of the agent dir. using 
        #cwd until we do something else.
        self.process = subprocess.Popen(args, cwd=working_dir, env=env)
        self.dirname = 'agent.{0}'.format(id(self))
        cgcreate('cpu', [self.path, self.dirname])
        cgcreate('memory', [self.path, self.dirname])
        #cgset('cpu', [self.path, self.dirname, 'cpu.cfs_quota_us'], str(self.cpu_quota))
        cgset('cpu', [self.path, self.dirname, 'tasks'], str(self.process.pid))
        cgset('memory', [self.path, self.dirname, 'memory.soft_limit_in_bytes'], str(self.memory))
        cgset('memory', [self.path, self.dirname, 'tasks'], str(self.process.pid))


class ResourceMonitor(object):
    def __init__(self, bogomips=None, memory=None, name='resmon'):
        if bogomips is None:
            bogomips = get_bogomips() * 0.8
        if memory is None:
            memory = get_total_memory() * 0.5
        self.total_bogomips = bogomips
        self.avail_bogomips = bogomips
        self.total_memory = memory
        self.avail_memory = memory
        self._out = {}
        self.dirname = '{0}.{1}'.format(name, id(self))
        cgcreate('cpu', [self.dirname])
        cgcreate('memory', [self.dirname])

    def __del__(self):
        cgremove('cpu', [], [self.dirname])
        cgremove('memory', [], [self.dirname])

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
            'platform.version': __version__,
            'memory.total': self.total_memory,
            'bogomips.total': self.total_bogomips,
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

        Examples of soft resources:
            cpu.bogomips
            memory.soft_limit_in_bytes
        '''
        failed = {}
        bogomips = float(contract.pop('cpu.bogomips', 0))
        if 0.0 < bogomips < 1.0:
            bogomips = self.total_bogomips * bogomips
        bogomips = int(bogomips)
        if not 0 < bogomips < self.avail_bogomips:
            failed['cpu.bogomips'] = self.avail_bogomips
        memory = float(contract.pop('memory.soft_limit_in_bytes', 0))
        if 0.0 < memory < 1.0:
            memory = self.total_memory * memory
        memory = int(memory)
        if not 0 < memory < self.avail_memory:
            failed['memory.soft_limit_in_bytes'] = self.avail_memory
        if contract:
            failed.update(dict.fromkeys(contract.keys()))
        if failed:
            return None, failed
        self.avail_bogomips -= bogomips
        self.avail_memory -= memory
        cpu_quota = int((float(bogomips) / self.total_bogomips) * 100000)
        execenv = ExecutionEnvironment(self.dirname, cpu_quota, memory)
        ref = weakref.ref(execenv, self._reclaim)
        self._out[id(ref)] = ref, id(execenv), bogomips, memory
        return execenv, None

    def _reclaim(self, ref):
        _, pid, bogomips, memory = self._out.pop(id(ref))
        self.avail_bogomips += bogomips
        self.avail_memory += memory
        name = 'agent.{0}'.format(pid)
        cgremove('cpu', [self.dirname], [name])
        cgremove('memory', [self.dirname], [name])


def require_resource_monitor(fn):
    '''Decorator to require a default resource monitor instance.'''
    def wrapper(*args, **kwargs):
        if _resource_monitor is None:
            raise ResourceError(
                    'no resource monitor has been set to handle requests')
        return fn(*args, **kwargs)
    functools.update_wrapper(wrapper, fn)
    return wrapper


@require_resource_monitor
def get_static_resources(query_items=None):
    return _resource_monitor.get_static_resources(query_items)
get_static_resources.__doc__ = ResourceMonitor.get_static_resources.__doc__

@require_resource_monitor
def check_hard_resources(contract):
    return _resource_monitor.check_hard_resources(contract)
check_hard_resources.__doc__ = ResourceMonitor.check_hard_resources.__doc__

@require_resource_monitor
def reserve_soft_resources(contract):
    return _resource_monitor.reserve_soft_resources(contract)
reserve_soft_resources.__doc__ = ResourceMonitor.reserve_soft_resources.__doc__


def set_resource_monitor(monitor):
    '''Set the default resource monitor.'''
    global _resource_monitor
    _resource_monitor = monitor

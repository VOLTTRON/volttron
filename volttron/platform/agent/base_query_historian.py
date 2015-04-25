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

from abc import abstractmethod
from collections import defaultdict
import logging
from pprint import pprint

from volttron.platform.agent.vipagent import RPCAgent, export, onevent
from volttron.platform.agent import utils
from dateutil.parser import parse 
import datetime
import pytz
import re
import dateutil

utils.setup_logging()
_log = logging.getLogger(__name__)

class BaseQueryHistorianAgent(RPCAgent):
    '''This is the base agent for query historian Agents. 
    It defines functions that must be defined to impliment the 
    
    Event processing in publish_to_historian and setup in historian_setup
    both happen in the same thread separate from the main thread. This is 
    to allow blocking while processing events. 
    '''

    @export()
    def query(self, topic=None, start=None, end=None, skip=0, count=None):
        """Actual RPC hanlder"""
        
        if topic is None:
            raise TypeError('"Topic" required')
            
        if start is not None:
            try:
                start = parse(start)
            except TypeError:
                start = time_parser.parse(start)
                
        if end is not None:
            try:
                end = parse(end)
            except TypeError:
                end = time_parser.parse(end)
        
        results = self.query_historian(topic, start, end, skip, count)
        metadata = results.get("metadata")
        if metadata is None:
            results['metadata'] = {}
        return results

    @abstractmethod
    def query_historian(self, topic, start=None, end=None, skip=0, count=None):
        """This function should return the results of a query in the form:
        {"values": [(timestamp1: value1), (timestamp2: value2), ...],
         "metadata": {"key1": value1, "key2": value2, ...}}
         
         metadata is not required (The caller will normalize this to {} for you)
        """
    
    @onevent('setup')
    def run_setup(self):
        self.historian_setup()
        
    def historian_setup(self):
        '''Optional setup routine, setup any needed db connection here.'''
    
#The following code is 
#Copyright (c) 2011, 2012, Regents of the University of California   
#and is under the same licence as the remainder of the code in this file.
#Modification were made to remove unneeded pieces and to fit with the
#intended use.
import ply
import ply.lex as lex
import ply.yacc as yacc
from dateutil.tz import gettz, tzlocal
local = tzlocal()

def now(tzstr = 'UTC'):
    '''Returns an aware datetime object with the current time in tzstr timezone'''
    if tzstr == 'Local':
        tz = local
    else:
        tz = gettz(tzstr)
    return datetime.datetime.now(tz)

def strptime_tz(str, format='%x %X', tzstr='Local'):
    '''Returns an aware datetime object. tzstr is a timezone string such as
       'US/Pacific' or 'Local' by default which uses the local timezone.
    '''
    dt = datetime.datetime.strptime(str, format)
    if tzstr == 'Local':
        tz = local
    else:
        tz = gettz(tzstr)
    return dt.replace(tzinfo = tz)

tokens = ('NOW',"QSTRING", 'LVALUE', 'NUMBER')

reserved = {
    'now' : 'NOW'}

literals = '()[]*^.,<>=+-/'

time_units = re.compile('^(d|days?|h|hours?|m|minutes?|s|seconds?)$')

def get_timeunit(t):
    if not time_units.match(t):
        raise ValueError("Invalid timeunit: %s" % t)
    if t.startswith('d'): return 'days'
    elif t.startswith('h'): return 'hours'
    elif t.startswith('m'): return 'minutes'
    elif t.startswith('s'): return 'seconds'
    
def t_QSTRING(t):
    r'("[^"\\]*?(\\.[^"\\]*?)*?")|(\'[^\'\\]*?(\\.[^\'\\]*?)*?\')'    
    if t.value[0] == '"':
        t.value = t.value[1:-1].replace('\\"', '"')
    elif t.value[0] == "'":
        t.value = t.value[1:-1].replace("\\'", "'")
    return t

def t_LVALUE(t):
    r'[a-zA-Z\~\$\_][a-zA-Z0-9\/\%_\-]*'
    t.type = reserved.get(t.value, 'LVALUE')
    return t

def t_NUMBER(t):
    r'([+-]?([0-9]*\.)?[0-9]+)'
    if '.' in t.value:
        try:
            t.value = float(t.value)
        except ValueError:
            print "Invalid floating point number", t.value
            t.value = 0
    else:
        try:
            t.value = int(t.value)
        except ValueError:
            print "Integer value too large %d", t.value
            t.value = 0
        
    return t
is_number = lambda x: isinstance(x, int) or isinstance(x, float)

t_ignore = " \t"
def t_newline(t):
    r'[\n\r]+'
    t.lexer.lineno += t.value.count("\n")

def t_error(t):
    raise ValueError("Syntax Error in Query")
    #print("Illegal character '%s'" % t.value[0])
    #t.lexer.skip(1)

smapql_lex = lex.lex()    

TIMEZONE_PATTERNS = [
    "%m/%d/%Y",
    "%m/%d/%Y %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    ]
def parse_time(ts):
    for pat in TIMEZONE_PATTERNS:
        try:
            return strptime_tz(ts, pat)
        except ValueError:
            continue
    raise ValueError("Invalid time string:" + ts)

def p_query_pair(t):
    """query : '(' timeref ',' timeref ')' """
    t[0] = (t[2], t[4])
    
def p_query_single(t):
    """query : timeref """
    t[0] = t[1]
                   
# an absolute time reference.  can be a unix timestamp, a date string,
# or "now"
def p_timeref(t):
    """timeref : abstime
               | abstime reltime"""
    t[0] = t[1]
    if len(t) == 2:
        ref = t[1]
    else:
        ref = t[1] + t[2]
    t[0] = ref

def p_abstime(t):
    """abstime : NUMBER 
               | QSTRING
               | NOW"""
    if t[1] == 'now':
        t[0] = now()
    elif type(t[1]) == type(''):
        t[0] = parse_time(t[1])
    else:
        t[0] = datetime.datetime.utcfromtimestamp(t[1] / 1000)

def p_reltime(t):
    """reltime : NUMBER LVALUE
               | NUMBER LVALUE reltime"""
    timeunit = get_timeunit(t[2])
    delta = datetime.timedelta(**{timeunit: t[1]})
    if len(t) == 3:
        t[0] = delta
    else:
        t[0] = t[3] + delta
        
# Error rule for syntax errors
def p_error(p):
    raise ValueError("Syntax Error in Query")

# Build the parser
time_parser = yacc.yacc(write_tables=0)
        
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
# }}}

from dateutil.parser import parse
from  volttron.platform.agent.utils import fix_sqlite3_datetime 
import pytest
import sqlite3 as sql


def test_sqlite_fixes():
    """This is all in a single test so we don't have to muck around with 
    reloading modules."""
    import python_2_7_3_sqlite3 as sql_old
    conn = sql_old.connect(':memory:', detect_types=sql_old.PARSE_DECLTYPES|sql_old.PARSE_COLNAMES)
    
    cur = conn.cursor()
    cur.execute("create table test(ts timestamp)")
    
    now_string = '2015-12-17 00:00:00.000005Z'
    now = parse(now_string)
    
    now_string_tz = '2015-12-17 00:00:00Z'
    now_tz = parse(now_string_tz)
    
    cur.execute("insert into test(ts) values (?)", (now,))
    
   # Verify that our private copy of sqlite3 from 2.7.3 does indeed break.
    try:
        cur.execute("select * from test")
        print "Did not raise expected exception"
        assert False
    except ValueError as e:
        assert e.message == "invalid literal for int() with base 10: '000005+00:00'"
     
    cur.execute("delete from test")   
    
    cur.execute("insert into test(ts) values (?)", (now_tz,))
    
    try:
        cur.execute("select * from test")
        print "Did not raise expected exception"
        assert False
    except ValueError as e:
        assert e.message == "invalid literal for int() with base 10: '00+00'"
        
    fix_sqlite3_datetime(sql_old)
    
    cur.execute("delete from test")  
    cur.execute("insert into test(ts) values (?)", (now,))
    
    cur.execute("select * from test")
    test_now = cur.fetchone()[0]
    
    cur.execute("delete from test")  
    cur.execute("insert into test(ts) values (?)", (now_tz,))
    
    cur.execute("select * from test")
    test_now_tz = cur.fetchone()[0]
    
    assert test_now == now
    assert test_now_tz == now_tz


def test_sqlite_fix_current():
    now_string = '2015-12-17 00:00:00.000005Z'
    now = parse(now_string)
    
    now_string_tz = '2015-12-17 00:00:00Z'
    now_tz = parse(now_string_tz)
    
    # Patch the global sqlite3
    fix_sqlite3_datetime()
    
    conn = sql.connect(':memory:', detect_types=sql.PARSE_DECLTYPES|sql.PARSE_COLNAMES)
    
    cur = conn.cursor()
    cur.execute("create table test(ts timestamp)")
    
    cur.execute("delete from test")  
    cur.execute("insert into test(ts) values (?)", (now,))
    
    cur.execute("select * from test")
    test_now = cur.fetchone()[0]
    
    cur.execute("delete from test")  
    cur.execute("insert into test(ts) values (?)", (now_tz,))
    
    cur.execute("select * from test")
    test_now_tz = cur.fetchone()[0]
    
    assert test_now == now
    assert test_now_tz == now_tz

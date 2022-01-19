# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

from dateutil.parser import parse
from  volttron.platform.agent.utils import fix_sqlite3_datetime
import sqlite3 as sql

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

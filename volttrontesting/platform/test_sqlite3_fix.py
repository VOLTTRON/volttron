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

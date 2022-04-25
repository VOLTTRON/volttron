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

from argparse import ArgumentParser
import sqlite3

from volttron.platform.agent.utils import parse_timestamp_string, format_timestamp


def main(database_name):
    db = sqlite3.connect(database_name)
    c = db.cursor()
    c.execute("select max(rowid) from data;")
    count = c.fetchone()[0]

    #Batches of 1000
    #We do this because of a bug in the sqlite implementation in python
    #which causes problems with nested cursors.
    for i in range(0, count, 1000):
        c.execute("select rowid, ts from data where rowid > ? order by rowid asc limit 1000;", (i,))
        rows = c.fetchall()
        print("processing rowid:", i+1, "to", i+len(rows))

        for rowid, ts in rows:
            #Skip already converted rows.
            if "T" in ts:
                continue

            new_ts = format_timestamp(parse_timestamp_string(ts))
            c.execute("update data set ts = ? where rowid = ?;", (new_ts, rowid))

        db.commit()

if __name__ == "__main__":
    parser = ArgumentParser(description="Update the timestamp format in a Sqlite Historians database in place. "
                            "This script corrects a problem comparing dates introduced by a format change in "
                            "VOLTTRON 4.1. Running this is only needed for SqliteHistorians data created in versions "
                            " of VOLTTRON prior to 4.1. It is recommended that the historian is not running while "
                            "this script is. It is recommended that you backup your database file before running this.")

    parser.add_argument('database',
                        help='The path to the database file.')

    args = parser.parse_args()
    main(args.database)

# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
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

import datetime
import os
from dateutil.relativedelta import relativedelta
from volttron.platform.dbutils.sqlitefuncts import SqlLiteFuncts

class SQLiteArchiverFuncts(SqlLiteFuncts):
    """
    Implementation of SQLite3 database operation for VOLTTRON Historian framework.  This implementation includes
    additional functionality for periodically archiving the SQLite database.
    :py:class:`sqlhistorian.historian.SQLHistorian` and
    :py:class:`sqlaggregator.aggregator.SQLAggregateHistorian`
    For method details please refer to base class
    :py:class:`volttron.platform.dbutils.basedb.DbDriver`
    """

    def __init__(self, connect_params, table_names, archive_period, archive_period_units):
        super(SqlLiteFuncts, self).__init__(connect_params, table_names)
        archive_period = int(archive_period)
        if archive_period_units not in ['m', 'd', 'w', 'h', 'M']:
            raise ValueError("Archive period units must be m (months), d (days), w (weeks), h (hours), M (minutes)")
        else:
            self.archive_period_units = archive_period_units
        if self.archive_period_units == 'w':
            archive_period = archive_period * 7
            self.archive_period_units = 'd'
        if self.archive_period_units == 'm':
            self.archive_period = relativedelta(months=+6)
        elif self.archive_period_units == 'd':
            self.archive_period = datetime.timedelta(days=archive_period)
        elif archive_period_units == 'h':
            self.archive_period = datetime.timedelta(hours=archive_period)
        else:
            self.archive_period = datetime.timedelta(minutes=archive_period)
        self.next_archive_time = datetime.datetime.now() + self.archive_period

    def manage_db_size(self, history_limit_timestamp, storage_limit_gb):
        """

        """
        # close the current connection and move the database using the rollover name
        if datetime.datetime.now() > self.next_archive_time:
            # Close the current database connection
            self.close()
            # move the database file that was created
            os.rename(self.__database, self.get_archive_db_path())
            # then reset the connnection (build a new database)
            self.cursor()
        else:



    def get_archive_timestamp_format(self):
        """
        :returns: Datetime formatting string for archive database names
        """
        if self.archive_period_units == 'm':
            return "%m-%Y"
        elif self.archive_period_units == 'd':
            return "%m-%d-%Y"
        elif self.archive_period_units == 'h':
            return "%m-%d-%Y_%H"
        elif self.archive_period_units == 'M':
            return "%m-%d-%Y_%H_%M"
        else:
            raise ValueError(f'Specified units for rollover DB not supported: {self.archive_period_units}')

    def get_archive_db_path(self):
        """
        :returns: Full path for the next archive database file
        """
        db_dir, db_name = self.__database.rsplit(".")
        db_prefix, db_suffix = db_name.rsplit(".")
        archive_db_timestamp = datetime.datetime.now().strftime(self.get_archive_timestamp_format())
        archive_db_name = ".".join([db_prefix, f'{archive_db_timestamp}', db_suffix])
        return os.path.join(db_dir, archive_db_name)

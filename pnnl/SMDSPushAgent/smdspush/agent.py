# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#

# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

#}}}

from contextlib import closing
from datetime import datetime
import logging
import sys
import time
from time import mktime
import json
import calendar

from volttron.platform.agent import BaseAgent, PublishMixin, periodic
from volttron.platform.agent import utils, matching
from volttron.platform.messaging import headers as headers_mod, topics


#import settings

import pyodbc


# Important environment variables
# ODBCSYSINI: Path prepended to odbcinst.ini; defaults to /etc
# ODBCINSTINI: Override odbcinst.ini file name; defaults to odbcinst.ini
# ODBCINI: Override path to odbc.ini; defaults to /etc/odbc.ini
# FREETDSCONF: Override path to freetds.conf; defaults to
#              /etc/freetds/freetds.conf

# At a minimum, odbcinst.ini file should be configured for FreeTDS.
# [FreeTDS]
# Description = FreeTDS Driver
# #Driver = /usr/lib/libtdsodbc.so
# Driver = /usr/lib/x86_64-linux-gnu/odbc/libtdsodbc.so
# Setup = /usr/lib/x86_64-linux-gnu/odbc/libtdsS.so
# UsageCount = 1

# Important tables: SMDSChannelMAP and sMAPOutputs


_connection_defaults = {
    'Driver': 'FreeTDS',
    'Port': 1433,
    'TDS_Version': 7.1,
    'ClientCharset': 'UTF-8',
    'TextSize': 64512,
    #'Server': None,
    #'Database': None,
    #'UID': None,
    #'PWD': None
}

_SELECT_POINTS = '''
SELECT map.*, MAX(UTC)
FROM SMDSChannelMap AS map
LEFT JOIN sMAPOutputs AS data ON map.DataChannelId = data.DataChannelId
GROUP BY map.DataChannelId, map.sMAPpath, map.YAxisName;
'''
#SMDSChannelMap.YAxisName , map.YAxisName

_SELECT_VALUES = '''
SELECT UTC, DataValue
FROM sMAPOutputs
WHERE {}
ORDER BY UTC;
'''

utils.setup_logging()
_log = logging.getLogger(__name__)


def TimestampFromDatetime(dt):
    return dt and int(calendar.timegm(dt.utctimetuple()))

def DatetimeFromValue(ts):
    if isinstance(ts, (int, long)):
        return datetime.utcfromtimestamp(ts)
    elif isinstance(ts, float):
        return datetime.utcfromtimestamp(ts)
    elif not isinstance(ts, datetime):
        raise ValueError('Unknown timestamp value')
    return ts


class Connection(object):
    def __init__(self, **kwargs):
        params = {key.upper(): val for key, val in
                  _connection_defaults.iteritems()}
        params.update({key.upper(): val for key, val in kwargs.iteritems()})
        connectstring = ';'.join(['{}={{{}}}'.format(
                str(k).replace('=', '=='), str(v).replace('}', '}}'))
                for k, v in params.iteritems()])
        self.connection = pyodbc.connect(connectstring)

    def get_points(self):
        with closing(self.connection.execute(_SELECT_POINTS)) as cursor:
            return [(chan_id, path, units, TimestampFromDatetime(dt))
                    for chan_id, path, units, dt in cursor]

    def get_values(self, chan_id, after=None, before=None):
        where = 'DataChannelId = ?'
        params = [chan_id]
        if after:
            where += ' AND UTC > ?'
            params.append(DatetimeFromValue(after))
        elif before:
            where += ' AND UTC < ?'
            params.append(DatetimeFromValue(before))
        with closing(self.connection.execute(
                _SELECT_VALUES.format(where), *params)) as cursor:
            return [(TimestampFromDatetime(dt), value) for dt, value in cursor]


def PushAgent(config_path, **kwargs):
    
    config = utils.load_config(config_path)
    def get_config(name):
        try:
            value = kwargs.pop(name)
        except KeyError:
            return config[name]

    agent_id = get_config('agentid')
    
    log_path = get_config('log_path')
    periodic_days = get_config('periodic_days')
    
    class Agent(PublishMixin, BaseAgent):
        '''This agent grabs data from a database then pushes that data to 
        sMAP based on the paths returned.
        
        On startup, it sets the latest time for all retrieved points to
        the start_time value. If this is <0 then it uses current time.
        After that, latest time is the value returned by the DB query.
        This has the potential for a problem if data fails to be
        inserted into sMAP since the agent will not request it again.
        
        '''
        #TODO: The agent should verify that data went into sMAP and the 
        #latest time for a point should be based on that, not on the
        # time returned by the DB.
        
        #TODO: Ideally, on startup the agent would try to find the
        #most recent time for each point in sMAP. Not sure there's
        #an easy query to do this through sMAP so may require 
        #backing up time range queries until you find data.
    
        def __init__(self, **kwargs):
            super(Agent, self).__init__(**kwargs)
            config = utils.load_config(config_path)
            self._connection_params = {
                    key.upper(): val for key, val in
                    config.get('connection', {}).iteritems()}
            for key in ['server', 'database', 'uid', 'pwd']:
                if key in kwargs:
                    self._connection_params[key.upper()] = kwargs.pop(key)
            self._last = {}
    
            self._start_time = get_config('start_time')
    
            # Set defaults then do immediate update based on the default time in the config
    
            self.set_defaults()
            self.do_update()
        
            
        
        def setup(self):
            # Always call the base class setup()
            super(Agent, self).setup()
            
        def set_defaults(self):
            conn = Connection(**self._connection_params)
            if (self._start_time < 0):
                self._start_time = time.time()
            
#             _log.debug(DatetimeFromValue(self._start_time))
            
            for chan_id, path, units, latest in conn.get_points():
                stamp = DatetimeFromValue(latest) if latest != None else ''
                
                self._last[chan_id] = self._start_time
                
                _log.debug('{chan}: {path} {units} - {latest}'.format(chan=chan_id, 
                                                     path=path, latest=stamp, units=units))
    
#         @periodic(periodic_days * 24 * 60 * 60)
        @periodic(60 * 60)
        def do_update(self):
            conn = Connection(**self._connection_params)
            for chan_id, path, units, latest in conn.get_points():
                _log.debug(str(chan_id) + " " + path + " " + str(DatetimeFromValue(self._last.get(chan_id))))
                values = conn.get_values(chan_id, self._last.get(chan_id))
                if values:
                    # Send them to sMAP
                    self._last[chan_id] = values[-1][0]
                    
                    time.sleep(3)
                    
                    self.log_to_smap(log_path, path, values, units)
                    
        def log_to_smap(self, log_source, path, values, units="Units"):
            '''Push data to sMAP. This will push data into a path off the 
            main source:  /Source/log_source/path. If logging data is 
            to go right beside real data, log source will need to be removed.
            '''
            _log.debug( path)
            headers = {}
            headers[headers_mod.FROM] = agent_id
            headers[headers_mod.CONTENT_TYPE] = headers_mod.CONTENT_TYPE.JSON
#             headers['SourceName'] = log_source
            
            # Split full path to get path and point name
            path_to_point = path[0:path.rfind('/')]
            point = path[path.rfind('/')+1:len(path)]
            
            content = {
                point: {
                    "Readings": values,
                    "Units": units,
                    "data_type": "double"
                }
            }
            topic = 'datalogger/log/'+log_source+path_to_point
            self.publish(topic, headers, json.dumps(content))
    
        @matching.match_headers({headers_mod.TO: agent_id})
        @matching.match_exact('datalogger/status')
        def on_logger_status(self, topic, headers, message, match):
            if  message != ["Success"]:
                _log.error("Logging attempt failed")
    
    Agent.__name__ = 'SMDSPushAgent'
    return Agent(**kwargs)
    

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.''' 
    try:
        utils.default_main(PushAgent,
                           description='SMDS Result Pushing agent',
                           argv=argv)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

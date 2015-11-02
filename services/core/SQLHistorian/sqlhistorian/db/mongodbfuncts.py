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
#}}}

#import errno
import logging
#import os
import importlib
from datetime import datetime
#from zmq.utils import jsonapi

from volttron.platform.agent import utils

utils.setup_logging()
_log = logging.getLogger(__name__)


class MongodbFuncts:

    def __init__(self, **kwargs):
        #kwargs['dbapimodule'] = 'mysql.connector'
        #super(MySqlFuncts, self).__init__('pymongo', **kwargs)
        self.__dbapimodule = "pymongo"
        _log.debug("Constructing Driver for "+ self.__dbapimodule)

        self.__dbmodule = importlib.import_module(self.__dbapimodule)
        self.__connection = None
        self.__connect_params = kwargs

        try:
            if not self.__check_connection():
                raise AttributeError(
                        "Couldn't connect using specified configuration"
                        " credentials")
        except Exception as e:
            _log.exception(e)
            raise AttributeError("Couldn't connect using specified "
                        "configuration credentials")

    def __check_connection(self):
        can_connect = False

        #conn = self.__dbmodule.connect(**self.__connect_params)
        conn = self.__connect(True)

        if conn:
            can_connect = True

        if can_connect:
            conn.close()

        return can_connect

    def __connect(self, return_val=False):
        mongo_uri = "mongodb://{user}:{passwd}@{host}:{port}/{database}".format(**self.__connect_params)
        if return_val:
            return self.__dbmodule.MongoClient(mongo_uri)

        if self.__connection == None:
            #self.__connection = self.__dbmodule.connect(**self.__connect_params)
            self.__connection = self.__dbmodule.MongoClient(mongo_uri)

    #TODO: see if Mongodb has commit and rollback (or something equivalent)
    def commit(self):
        pass

    def rollback(self):
        pass

        
    def query(self, topic, start=None, end=None, skip=0,
                            count=None, order="FIRST_TO_LAST"):
        """This function should return the results of a query in the form:
        {"values": [(timestamp1, value1), (timestamp2, value2), ...],
         "metadata": {"key1": value1, "key2": value2, ...}}

         metadata is not required (The caller will normalize this to {} for you)
        """
        self.__connect()
        if self.__connection is None:
            return False
        db = self.__connection[self.__connect_params["database"]]
        #Find topic_id for topic
        row = db["topics"].find_one({"topic_name": topic})
        id_ = row.topic_id
        #
        order_by = 1
        if order == 'LAST_TO_FIRST':
            order_by = -1
        if start is not None:
            start = datetime.datetime(2000, 1, 1, 0, 0, 0)
        if end is not None:
            end = datetime.datetime(3000, 1, 1, 0, 0, 0)
        if count is None:
            count = 100
        skip_count = 0
        if skip > 0:
            skip_count = skip

        _log.debug("About to do real_query")

        cursor = db["data"].find({
                    "topic_id": id_,
                    "ts": { "$gte": start, "$lte": end},
                }).skip(skip_count).limit(count).sort( { "ts": order_by } )

        values = [(document.ts.isoformat(), document.value) for document in cursor]

        return {'values': values}
    
    def insert_data(self, ts, topic_id, data):
        self.__connect()
        if self.__connection is None:
            return False

        db = self.__connection[self.__connect_params["database"]]

        id_ = db["data"].insert({
            "ts": ts,
            "topic_id": topic_id,
            "value": data})

        return True
        
    def insert_topic(self, topic):
        self.__connect()

        if self.__connection is None:
            return False
        db = self.__connection[self.__connect_params["database"]]
        id_ = db["topics"].insert({"topic_name": topic})
        row = [id_]

        return row
    
    def get_topic_map(self):
        self.__connect()
        if self.__connection is None:
            return False
        db = self.__connection[self.__connect_params["database"]]
        cursor = db["topics"].find()
        return dict([(document.topic_name, document.id_) for document in cursor])

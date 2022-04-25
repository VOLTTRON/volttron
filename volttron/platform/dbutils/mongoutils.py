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

import _sre
import re
import socket
# reload to get the socket that is not patched by gevent.
# pika requires socket patched and thread not patched
# pymongo requires either both patched (to support gevent) or both unpatched to use threads
from importlib import reload
reload(socket)

import pymongo
import logging

_log = logging.getLogger(__name__)
__version__ = '0.2'


def get_mongo_client(connection_params, **kwargs):
            database_name = connection_params['database']
            hosts = connection_params['host']
            ports = connection_params['port']
            user = connection_params['user']
            passwd = connection_params['passwd']

            if isinstance(hosts, list):
                if not ports:
                    hosts = ','.join(hosts)
                else:
                    if len(ports) != len(hosts):
                        raise Exception(
                            'port an hosts must have the same number of items'
                        )
                    hostports = list(zip(hosts, ports))
                    hostports = [str(e[0]) + ':' + str(e[1]) for e in
                                 hostports]
                    hosts = ','.join(hostports)
            else:
                if isinstance(ports, list):
                    raise Exception(
                        'port cannot be a list if hosts is not also a list.'
                    )
                hosts = '{}:{}'.format(hosts, ports)

            params = {'hostsandports': hosts, 'user': user,
                      'passwd': passwd, 'database': database_name}

            mongo_uri = "mongodb://{user}:{passwd}@{hostsandports}/{database}"
            if connection_params.get('authSource'):
                mongo_uri = mongo_uri + '?authSource={authSource}'
                params['authSource'] = connection_params['authSource']
            mongo_uri = mongo_uri.format(**params)
            mongoclient = pymongo.MongoClient(mongo_uri, **kwargs)

            return mongoclient


def get_topic_map(client, topics_collection):
    _log.debug("In get topic map")
    db = client.get_default_database()
    cursor = db[topics_collection].find()
    topic_id_map = dict()
    topic_name_map = dict()
    for document in cursor:
        topic_id_map[document['topic_name'].lower()] = document['_id']
        topic_name_map[document['topic_name'].lower()] = \
            document['topic_name']
    _log.debug("Returning map from get_topic_map")
    return topic_id_map, topic_name_map


def get_agg_topic_map(client, agg_topics_collection):
    _log.debug('loading agg topic map')
    topic_id_map = dict()
    db = client.get_default_database()
    cursor = db[agg_topics_collection].find()

    for document in cursor:
        topic_id_map[
            (document['agg_topic_name'].lower(),
             document['agg_type'],
             document['agg_time_period'])] = document['_id']
    _log.debug('returning agg topics map')
    return topic_id_map

def get_agg_topics(client, agg_topics_collection, agg_meta_collection):
    _log.debug('loading agg topics for rpc call')
    db = client.get_default_database()
    cursor = db[agg_meta_collection].find()
    meta_map = dict()
    for document in cursor:
        meta_map[document['agg_topic_id']] =  document['meta']

    cursor = db[agg_topics_collection].find()
    agg_topics = []
    for document in cursor:
        _log.debug("meta_map[document['_id'] is {}".
                   format(meta_map[document['_id']]))
        agg_topics.append(
            (document['agg_topic_name'].lower(),
             document['agg_type'],
             document['agg_time_period'],
             meta_map[document['_id']]['configured_topics']))
    _log.debug('returning agg topics for rpc call')
    return agg_topics


def get_tagging_queries_from_ast(tup, tag_refs, sub_queries):
    mongo_operators = {'and': "$and", "or": "$or"}
    #_log.debug("In get mongo query condition. tup: {}".format(tup))
    condition = dict()
    if tup is None:
        return tup
    if not isinstance(tup[1], tuple):
        left = tup[1]
    else:
        left = get_tagging_queries_from_ast(tup[1], tag_refs, sub_queries)
    if not isinstance(tup[2], tuple):
        right = tup[2]
    else:
        right = get_tagging_queries_from_ast(tup[2], tag_refs, sub_queries)

    assert isinstance(tup[0], str)

    # Verify first for parent tag
    if isinstance(left, str):
        tags = left.split(".")
        if len(tags) == 2:
            # Process parent tag first
            # Convert campusRef.geoPostalCode="20500" to
            # sub query - campus=True AND geoPostalCode="20500", results of
            # this would get place in campusRef in [<result>]
            new_tup = ('AND', ('=', tag_refs[tags[0]], True),
                       (tup[0], tags[1], right))
            sub_queries.append(get_tagging_queries_from_ast(new_tup,
                                                            tag_refs,
                                                            None))
            return {tags[0]:{"$in":"##VOLTTRON_Q"+str(len(sub_queries))}}

    lower_tup0 = tup[0].lower()
    # Check for negation. negation needs to be handled as special case
    if lower_tup0 == 'not':
        return _negate_condition(right)
    elif lower_tup0 in mongo_operators:
        # if or/and rhs should be array
        return {mongo_operators.get(lower_tup0): [left, right]}
    elif lower_tup0 == 'like':
        # LIKE is a special case. To negate {operator:{$regex:value}}
        # {operator:{$not:{$regex:value}}} since $not doesn't support
        # regex string. To negate use{operator:{$not:/value/}}
        # To keep it consistent, we compile the pattern in python for both
        # LIKE and NOT (LIKE operation)
        return {left: re.compile(right)}
    else:
        condition[left] = _get_mongo_comp_expr(tup[0], right)
        return condition


def _get_mongo_comp_expr(operator, operand):
    """
    Return the mongo syntax for given comparison operator.
    :param operator: comparison operator. >,<.>= etc.
    :param operand: rhs of the operation
    :return: mongo syntax for rhs of expression.
    """
    if operator == ">=":
        return {'$gte': operand}
    elif operator == "<=":
        return {'$lte': operand}
    elif operator == ">":
        return {'$gt': operand}
    elif operator == "<":
        return {'$lt': operand}
    elif operator == "=":
        return operand
    elif operator == "!=":
        return {'$ne': operand}


def _negate_condition(condition):
    """
    change not:{left:right} to left:{not:right}
    if right is a expression change and operator to or and vice versa.

    # Should be an instance of dic always

    :param condition:
    :return:
    """

    if isinstance(condition, dict):
        key, value = condition.popitem()
        process_values = False
        # check for NOT(key=value)
        if not isinstance(value, dict) and not isinstance(value, list) and \
                not isinstance(value, type(re.compile("test"))):
            return {key: {'$ne': value}}

        # any other case (>, <, like etc) will be a dict
        if key == '$and':
            key = '$or'
            process_values = True  # value would be a list
        elif key == '$or':
            key = '$and'
            process_values = True  # value would be a list

        new_value = []
        if process_values and isinstance(value, list):
            for v in value:
                if isinstance(v, dict):
                    # nested expression with and/or
                    new_value.append(_negate_condition(v))
                else:
                    new_value.append(v)
            return {key: new_value}
        else:
            return {key: {'$not': value}}

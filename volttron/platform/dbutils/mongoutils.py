import re

import pymongo
import logging

_log = logging.getLogger(__name__)
__version__ = '0.1'

def get_mongo_client(connection_params):

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
                        raise StandardError(
                            'port an hosts must have the same number of items'
                        )
                    hostports = zip(hosts, ports)
                    hostports = [str(e[0]) + ':' + str(e[1]) for e in
                                 hostports]
                    hosts = ','.join(hostports)
            else:
                if isinstance(ports, list):
                    raise StandardError(
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
            mongoclient = pymongo.MongoClient(mongo_uri)

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

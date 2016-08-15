
import pymongo
from bson.objectid import ObjectId
from pymongo import InsertOne, ReplaceOne
from pymongo.errors import BulkWriteError

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
            mongo_uri = mongo_uri.format(**params)
            mongoclient = pymongo.MongoClient(mongo_uri)

            return mongoclient


def get_topic_map(client,topics):
    db = client.get_default_database()
    cursor = db[topics].find()
    topic_id_map = dict()
    topic_name_map = dict()
    for document in cursor:
        topic_id_map[document['topic_name'].lower()] = document[
            '_id']
        topic_name_map[document['topic_name'].lower()] = \
            document['topic_name']
    return topic_id_map, topic_name_map

def find_topics_by_pattern(client, topics_collection, topics_pattern):
    db = client.get_default_database()
    pattern = { 'topic_name': '/'+topics_pattern+'/i' }
    cursor = db[topics_collection].find(pattern)
    topic_id_map = dict()
    topic_name_map = dict()
    for document in cursor:
        topic_id_map[document['topic_name'].lower()] = document[
            '_id']
        topic_name_map[document['topic_name'].lower()] = \
            document['topic_name']
    return topic_id_map, topic_name_map
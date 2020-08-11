"""
Utility script to read the list of topics from mongodb and insert mandatory
id and reference tags for these topics. The script only works for topics
with the naming convention campus/building/device/<optional sub device>/point.
A error will be displayed for any topics that do not conform to this naming
convention and will be skipped.

**Configure user configuration variables right below imports before running the
scripts.**

By default the script only set id field and parent references but if there are
other common tags that apply to ALL campus, building, device, or point, you
could update the tags variable in get_campus_tags, get_site_tags,
get_equip_tags, and get_point_tags method respectively
"""

import random
import re
import sqlite3
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
import datetime

# --- User configuration - start --- #

# Connection string to the mongo db from which list of topics should be read
topics_connection_string = "mongodb://<user>:<password>@vc-db.pnl.gov" \
                           ":27017" \
                           "/<db_name>"
topic_table = "topics"
# Regular expression that matches all device topics that conform to the
# naming pattern campus/building/device/<optional sub device>/point
device_topics = "^PNNL"

# table or collection name into which tags should be saved.
tags_table = "topic_tags_4"

# The connection details of the database into which tag tables are to be
# created.
# set mongo, sqlite or both. If you need tags to be saved in mongodb you can
#  set sqlite connection string as empty/None and vice-versa
tags_db_mongo_conn_str = "mongodb://test:test@localhost:27017/mongo_test"
tags_db_sqlite = "/home/velo/tags_test3.sqlite"

# --- User configuration - end --- #

write_to_mongo = False
if tags_db_mongo_conn_str:
    topics_mongodb = MongoClient(topics_connection_string).get_default_database()
    tags_client = MongoClient(tags_db_mongo_conn_str)
    tags_mongodb = tags_client.get_default_database()
    mongo_bulk = tags_mongodb[tags_table].initialize_ordered_bulk_op()
    mongo_batch_size = 0
    mongo_max_batch_size = 5000
    write_to_mongo = True

write_to_sqlite = False
if tags_db_sqlite:
    sqlite_connection = sqlite3.connect(
        tags_db_sqlite,
        detect_types = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    sqlite_connection.execute("PRAGMA CACHE_SIZE=-2000")

    sqlite_connection.execute("CREATE TABLE IF NOT EXISTS " + tags_table +
                              "("
                              "topic_prefix TEXT NOT NULL, "
                              "tag TEXT NOT NULL, "
                              "value TEXT, "
                              "UNIQUE(topic_prefix, tag) )")
    sqlite_connection.execute("CREATE INDEX IF NOT EXISTS idx_topic_prefix ON " +
                             tags_table + "(topic_prefix ASC);")
    sqlite_connection.execute("CREATE INDEX IF NOT EXISTS idx_tag ON " +
                             tags_table + "(tag ASC);")
    sqlite_bulk = []
    sqlite_batch_size = 0
    sqlite_max_batch_size = 100
    write_to_sqlite = True


def get_campus_tags(campus):
    tags = {
        "id": campus,
        "campus": True
    }

    # Additional common campus tags that could be added, for example if
    # all the devices are in the same campus you could set the address and
    # timezone details to the tag's dictionary. For example
    # tags = {"id": campus,
    #     "dis": "campus description ",
    #     "campus": True, "geoCountry": "US", "geoCity": "Washington D.C.",
    #     "geoPostalCode":"20500", "tz": "New_York"}

    return tags


def get_site_tags(campus, site):
    # Additional common site(i.e. building) tags could be added.
    # For example if all the buildings are in the same timezone, timezone
    # could be set. If all devices are from the same building then address
    # details could be added
    # tags = {
    #     "id": site,
    #     "site":True,
    #     "campusRef": campus,
    #     "yearBuilt": random.randint(1990, 2014),
    #     "geoAddr": " 100 Pennsylvania Avenue NW, Washington, DC",
    #     "geoStreet":"1 Pennsylvania Ave NW",
    #     "geoCity": "Washington D.C.",
    #     "geoCountry": "US",
    #     "geoPostalCode": "20500",
    #     "geoCoord": "C(38.898, -77.037)",
    #     "tz": "New_York"
    # }
    tags = {"id": site,
            "site":True,
            "campusRef": campus
    }

    return tags


def get_equip_tags(campus, site, parent_equip, equip):
    tags = {"id": equip,
            "equip": True,
            "campusRef": campus,
            "siteRef": site
            }
    if parent_equip:
        tags["equipRef"] = parent_equip
    return tags


def get_point_tags(campus, site, equip, point):
    tags = {"id": point,
            "point": True,
            "campusRef": campus,
            "siteRef": site,
            "equipRef": equip
            }
    return tags


def db_insert(tags, execute_now=False):
    r1 = r2 = True
    if write_to_sqlite:
        r2 = sqlite_insert(tags, execute_now)
    if write_to_mongo:
        r1 = mongo_insert(tags, execute_now)
    return r1 and r2


def mongo_insert(tags, execute_now=False):
    global mongo_bulk, mongo_batch_size, mongo_max_batch_size
    errors = False
    if tags:
        tags['_id'] = tags['id']
        # if not tags.get('topic_prefix'):
        #     tags['topic_prefix'] = tags['_id'][1:]
        mongo_bulk.insert(tags)
        mongo_batch_size += 1
    if mongo_batch_size > mongo_max_batch_size or execute_now:
        try:
            result = mongo_bulk.execute()
            if result['nInserted'] != mongo_batch_size:
                print ("bulk execute result {}".format(result))
                errors = True
        except BulkWriteError as ex:
            print(str(ex.details))
            errors = True
        finally:
            mongo_batch_size = 0
            mongo_bulk = tags_mongodb[tags_table].initialize_ordered_bulk_op()
    return errors


def sqlite_insert(tags, execute_now=False):
    global sqlite_bulk, sqlite_batch_size, sqlite_max_batch_size

    if tags:
        topic_prefix = tags["id"]
        for k, v in tags.items():
            if isinstance(v, bool):
                if v:
                    v = 1
                else:
                    v = 0
            sqlite_bulk.append((topic_prefix, k, v))
        # print sqlite_bulk
        sqlite_batch_size += len(tags)

    errors = False
    if sqlite_batch_size > sqlite_max_batch_size or execute_now:
        # print("Execute many")
        sqlite_connection.executemany("insert into " +
                                      tags_table + "(topic_prefix, "
                                      "tag, value) values (?,?,?)",
                                      sqlite_bulk)
        sqlite_connection.commit()
        sqlite_bulk = []
        sqlite_batch_size = 0


def db_close():
    sqlite_connection.close()
    tags_client.close()
    topics_mongodb.client.close()


def insert_topic_tags():
    cursor = topics_mongodb.topics.find(
        {"topic_name": re.compile(device_topics)}).sort("topic_name")
    current_campus = ""
    current_site = ""
    current_equip = ""
    current_sub_equip = ""
    current_point = ""
    n = 0
    for row in cursor:
        # print row
        parts = row["topic_name"].split("/")
        num_parts = len(parts)
        if num_parts == 4 or num_parts == 5:
            n += 1
            if current_campus != parts[0]:
                db_insert(get_campus_tags(parts[0]))
                current_campus = parts[0]

            site = "/".join(parts[:2])
            if current_site != site:
                db_insert(get_site_tags(parts[0], site))
                current_site = site

            equip = "/".join(parts[:3])
            if current_equip != equip:
                db_insert(get_equip_tags(parts[0], site, None, equip))
                current_equip = equip

            if num_parts == 5:
                sub_equip = "/".join(parts[:4])
                if current_sub_equip != sub_equip:
                    db_insert(get_equip_tags(parts[0], site, equip, sub_equip))
                    current_sub_equip = sub_equip

            point = "/".join(parts)
            if current_point != point:
                db_insert(get_point_tags(parts[0], site, "/".join(parts[:-1]),
                                         point))
                current_point = point
        else:
            print("Unrecognized topic pattern:{}".format(row["topic_name"]))
    if n > 0:
        db_insert(None, True)


if __name__ == '__main__':
    insert_topic_tags()
    db_close()


import random

import re
import sqlite3
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
import datetime

topics_connection_string = "mongodb://<user>:<password>@vc-db.pnl.gov" \
                           ":27017" \
                           "/prod_historian"
topic_table = "topics"
# device_topics = \
#     "^PNNL/SEB/AHU1/VAV123A/TerminalBoxDamperCommand|^PNNL/SEB/CHWS" \
#     "/HeatExchangeRate|PNNL_SEQUIM/.*"
device_topics = "^PNNL"
topics_mongodb = MongoClient(topics_connection_string).get_default_database()

tags_connection_string = "mongodb://test:test@localhost:27017/mongo_test"
tags_table = "topic_tags_2"
tags_client = MongoClient(tags_connection_string)
tags_mongodb = tags_client.get_default_database()
mongo_bulk = tags_mongodb[tags_table].initialize_ordered_bulk_op()
mongo_batch_size = 0
mongo_max_batch_size = 5000

sqlite_connection = sqlite3.connect(
    "/home/velo/tags_test2.sqlite",
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


def get_campus_tags(campus):
    tags = {
        "id":campus,
        "dis": "campus description {}".format(random.randint(5000, 10000)),
        "campus":True,
        "geoCountry": "US",
        "geoCity": "Washington D.C.",
        "geoPostalCode": random.choice(["20500","20501"]),
        "tz": "New_York"
    }

    return tags


def get_site_tags(campus, site):
    n = random.randint(1000, 2000)
    tags = {
        "id": site,
        "site":True,
        "campusRef": campus,
        "dis": "site description {}".format(random.randint(5000, 10000)),
        "yearBuilt": random.randint(1990, 2014),
        "area": random.randint(2000, 4000),
        "unit": "square_foot",
        "geoAddr": "{} Pennsylvania Avenue NW, Washington, DC".format(n),
        "geoStreet":"{} Pennsylvania Ave NW".format(n),
        "geoCity": "Washington D.C.",
        "geoCountry": "US",
        "geoPostalCode": "20500",
        "geoCoord": "C(38.898, -77.037)",
        "tz": "New_York"
    }

    return tags


def get_equip_tags(campus, site, parent_equip, equip):
    equip_type = random.choice(["ahu", "boiler","chiller","tank","vav"])
    tag1 = "equip_tag {}".format(random.randint(1, 5))
    tag2 = "equip_tag {}".format(random.randint(6, 10))
    tag3 = "equip_tag {}".format(random.randint(6, 10))
    tags =  {"id": equip,
            "equip": True,
            "campusRef": campus,
            "siteRef": site,
            "dis":"random description {}".format(random.randint(1,5000)),
            equip_type : True,
            tag1: random.randint(1, 5),
            tag2: random.randint(1, 5),
            tag3: random.randint(1, 5)
            }
    if parent_equip:
        tags["equipRef"] = parent_equip

    return tags


def get_point_tags(campus, site, equip, point):
    tag1 = "tag_{}".format(random.randint(1, 25))
    tag2 = "tag_{}".format(random.randint(26, 50))
    tag3 = "tag_{}".format(random.randint(51, 55))
    tag4 = "tag_{}".format(random.randint(60, 65))
    tag5 = "tag_{}".format(random.randint(70, 75))
    tags = {"id": point,
            "point": True,
            "campusRef": campus,
            "siteRef": site,
            "equipRef": equip,
            "dis": "random description {}".format(random.randint(1, 5000)),
            tag1 : random.randint(1, 500),
            tag2: random.randint(1, 500),
            tag3: random.randint(1, 500),
            tag4: random.choice([True, False]),
            tag5: "str {}".format(random.randint(0,10))
            }

    return tags


def db_insert(tags, execute_now=False):
    r1 = r2 = True
    r2 = sqlite_insert(tags, execute_now)
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


def test_tags():
    test_mongo_tags()


def test_mongo_tags():

    start = datetime.datetime.now()
    tags_cursor = tags_mongodb[tags_table].find(
        {"campus": True, "geoPostalCode": "20501"}, {"_id": 1})
    refs = [record['_id'] for record in tags_cursor]
    print("campus:True geoPostalCode:20501 result:{}".format(refs))
    tags_cursor = tags_mongodb[tags_table].find(
        {"campusRef": {"$in": refs}, "equip": True, "ahu": True,
         "equip_tag 7": {"$gt": 2}}, {"topic_prefix": 1})
    topics = [record['_id'] for record in tags_cursor]
    print("example query result: {}".format(topics))
    print ("Time taken by mongo for result: {}".format(
        datetime.datetime.now() - start))


def test_sqlite_tags():
    start = datetime.datetime.now()
    tags_cursor = sqlite_connection.execute(
        'select topic_prefix from test_tags where tag="campusRef" and value '
        'IN ( '
        '  '
        'select value from test_tags where tag="id" and topic_prefix IN ('
        '    select topic_prefix from test_tags where tag="campus" and '
        'value=1 '
        '    INTERSECT '
        '    select topic_prefix  from test_tags where tag="geoPostalCode"  '
        'and '
        '       value="20501")'
        ') '
        ' INTERSECT '
        'select topic_prefix from test_tags where tag="equip" and value=1 '
        ' INTERSECT '
        'select topic_prefix from test_tags where tag="ahu" and value=1 '
        ' INTERSECT '
        'select topic_prefix from test_tags where tag = "equip_tag 7" and '
        'value > 2')
    print ("topics :{}".format(tags_cursor.fetchall()))
    print ("Time taken by sqlite for result: {}".format(
        datetime.datetime.now() - start))


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
        parts = row["topic_name"].split("/")
        num_parts = len(parts)
        if num_parts == 4 or num_parts == 5:
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
    insert_topic_tags()  # now perform test query and time them
    test_tags()
    db_close()


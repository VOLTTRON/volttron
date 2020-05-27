import re
import datetime
from pymongo import MongoClient
from bson import ObjectId
client = MongoClient("mongodb://reader:volttronReader@172.26.63.4:27017"
                     "/2017_production_external?authSource=admin")
db = client.get_default_database()
regex = re.compile("^Economizer_RCx|^Airside_RCx", re.IGNORECASE)

cursor = db['topics'].find({"topic_name": regex})
ids_dicts = list(cursor)
#ids = [x['_id'] for x in ids_dicts]
#count = db.data.find({"topic_id":{"$in":ids}}).count()
start = datetime.datetime.now()
count = 0
start_date = '01Jan2016T00:00:00.000'
end_date = '14Mar2017T00:00:00.000'
s_dt = datetime.datetime.strptime(start_date, '%d%b%YT%H:%M:%S.%f')
e_dt = datetime.datetime.strptime(end_date, '%d%b%YT%H:%M:%S.%f')
for x in ids_dicts:
    count = count + db.data.find(
        {"topic_id":x['_id'],
         "ts":{"$gte":s_dt, "$lt":e_dt}}).count()
print (count)
print ("time taken: {}".format(datetime.datetime.now()-start))
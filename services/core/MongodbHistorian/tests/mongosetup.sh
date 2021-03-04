#!/bin/bash -e

# Installs MongoDB 4.4 Community Edition on Ubuntu 18.04 (Bionic)
# Script based upon mongodb installation at
# https://docs.mongodb.org/manual/tutorial/install-mongodb-on-ubuntu/

# Import the public key used by the package management system
wget -qO - https://www.mongodb.org/static/pgp/server-4.4.asc | sudo apt-key add -

# Create a list file for MongoDB
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu bionic/mongodb-org/4.4 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.4.list

# Install the MongoDB packages for 4.4.4
sudo apt-get update
sudo apt-get install -y mongodb-org=4.4.4 \
mongodb-org-server=4.4.4 \
mongodb-org-shell=4.4.4 \
mongodb-org-mongos=4.4.4 \
mongodb-org-tools=4.4.4

#echo "mongodb-org hold" | sudo dpkg --set-selections
#echo "mongodb-org-server hold" | sudo dpkg --set-selections
#echo "mongodb-org-shell hold" | sudo dpkg --set-selections
#echo "mongodb-org-mongos hold" | sudo dpkg --set-selections
#echo "mongodb-org-tools hold" | sudo dpkg --set-selections
#
#sudo cp ./services/core/MongodbHistorian/tests/mongod.conf /etc/mongod.conf
#sudo chown root.root /etc/mongod.conf

sudo service mongod restart

# Create the admin user that will create the test user
mongo admin --eval 'db.createUser( {user: "mongodbadmin", pwd: "V3admin", roles: [ { role: "userAdminAnyDatabase", db: "admin" }]});'
# Create test user that will be used in the integration tests
# 'mongo_test' is the test_database defined in services/core/MongodbHistorian/tests/fixtures.py
# Moreover, the user and password for the 'db.createUser' command should match the user and password defined in mongo_connection_param() in services/core/MongodbHistorian/tests/fixtures.py
mongo mongo_test -u mongodbadmin -p V3admin --authenticationDatabase admin --eval 'db.createUser( {user: "historian", pwd: "historian", roles: [ { role: "readWrite", db: "mongo_test" }]});'

#!/bin/bash -e

# Script based upon mongodb installation at
# https://docs.mongodb.org/manual/tutorial/install-mongodb-on-ubuntu/
os_version=""
mongo_version=3.2
function exit_on_error {
    rc=$?
    if [[ $rc != 0 ]]
    then
        printf "\n## Script could not complete successfully because of above error## \n"
        exit $rc
    fi

}

# validate sudo access
sudo -v
exit_on_error

while true; do
    printf "Enter 1 or 2 based on the version of Ubuntu you are running\n"
    printf "1. Ubuntu 12.04 LTS(Precise Pangolin)\n"
    printf "2. Ubuntu 14.04.4 LTS(Trusty Tahr)\n"
    read os_version

    if [ "$os_version" == "1" ]
    then
        os_version="ubuntu precise"
        break
    elif [ "$os_version" == "2" ]
    then
        os_version="ubuntu trusty"
        break
    else
        printf "Please enter 1 or 2. \n"
    fi
done

if [ $mongo_version == 3.0 ]
then
    sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 7F0CEB10
elif [ $mongo_version == 3.2 ]
then
    sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv EA312927
fi
exit_on_error
echo "deb http://repo.mongodb.org/apt/"$os_version"/mongodb-org/"$mongo_version" multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-"$mongo_version".list
exit_on_error

sudo apt-get update
exit_on_error

sudo apt-get install -y mongodb-org
exit_on_error

#Using default config so commenting below two lines
#sudo cp ./services/core/MongodbHistorian/tests/mongod.conf /etc/mongod.conf
#sudo chown root.root /etc/mongod.conf

sudo service mongod restart
exit_on_error
## Create users for the database.

printf "\n## Setting up admin user' ##\n"

printf "\nEnter admin username[admin]: "
read admin_user
if [ "$admin_user" == "" ]
then
    admin_user="admin"
fi

while true; do
    printf "Enter admin password: "
    read admin_passwd
    if [ "$admin_passwd" != "" ]
    then
        break
    else
        printf "Please enter non empty password\n"
    fi
done

printf "\n## Setting up users and database collection to be used by historian' ##\n"

printf "\nEnter volttron db name. This would be used by historian agents to store data[historian]: "
read db_name
if [ "$db_name" == "" ]
then
    db_name="historian"
fi

printf "\nEnter volttron db user name. This would be used by historian agents to acess "$db_name" collection[volttron]: "
read volttron_user
if [ "$volttron_user" == "" ]
then
    volttron_user="volttron"
fi

while true; do
    printf "Enter volttron db user password: "
    read volttron_passwd
    if [ "$volttron_passwd" != "" ]
    then
        break
    else
        printf "Please enter non empty password\n"
    fi
done

mongo admin --eval 'db.createUser( {user: "'$admin_user'", pwd: "'$admin_passwd'", roles: [ { role: "userAdminAnyDatabase", db: "admin" }]});'
exit_on_error
mongo $db_name -u $admin_user -p $admin_passwd --authenticationDatabase admin --eval 'db.createUser( {user: "'$volttron_user'", pwd: "'$volttron_passwd'", roles: [ { role: "readWrite", db: "'$db_name'" }]});'
exit_on_error
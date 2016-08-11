#!/bin/bash
#Install monogdb in centos/rhel as root.

#UPDATE the below two variables before running.
#mongodb version
mongo_version=3.2
#os_version. Valid values are "6" and "7"
os_version=""

while true; do
    printf "Enter the major version of your Redhat/Cent OS [6|7]: "
    read os_version
    if [ "$os_version" == "6" ] || [ "$os_version" == "7" ]
    then
        break
    else
        printf "6 and 7 are the only compatible versions\n"
    fi
done

config_file="/etc/yum.repos.d/mongodb-org-"$mongo_version".repo"
if [ -f $config_file ]
then
    printf "\n## Using existing $config_file file ##\n\n"
else
    sudo printf "[mongodb-org-"$mongo_version"]\n" >> $config_file
    sudo printf "name=MongoDB Repository\n" >> $config_file
    sudo printf "baseurl=https://repo.mongodb.org/yum/redhat/"$os_version"/mongodb-org/"$mongo_version"/x86_64/\n" >> $config_file
    sudo printf "gpgcheck=0\n" >> $config_file
    sudo printf "enabled=1\n" >> $config_file
    sudo printf "gpgkey=https://www.mongodb.org/static/pgp/server-"$mongo_version".asc\n" >> config_file
fi

printf "\n## Installing mongodb ##\n\n"
sudo yum install -y mongodb-org

printf "\n## Enabling default port for mongodb ##\n"
sudo yum install -y policycoreutils-python

sudo semanage port -a -t mongod_port_t -p tcp 27017

printf "\n## Starting mongodb. To stop use the command 'service mongod stop' ##\n"
sudo service mongod restart

# Create users for the database.
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
mongo $db_name -u $admin_user -p $admin_passwd --authenticationDatabase admin --eval 'use '"$db_name"'; db.createUser( {user: "'$volttron_user'", pwd: "'$volttron_passwd'", roles: [ { role: "readWrite", db: "'$db_name'" }]});'

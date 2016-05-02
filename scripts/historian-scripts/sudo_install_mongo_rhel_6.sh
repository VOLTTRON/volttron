#!/bin/bash
#Install monogdb in centos/rhel as root. Change mongodb version and os_version
#to appropriate version number before running

#UPDATE the below two variables before running.
#mongodb version
mongo_version=3.2
#os_version. Valid values are "6" and "7"
os_version="6"


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
printf "\n## Starting mongodb. To stop use the command 'service mongod sttop' ##\n"
sudo service mongod start

#!/bin/bash

#Script to install mongodb from source. reads install_mongodb.cfg from the
#same directory as this script
script_dir=`dirname $0`
download_url="https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-3.2.4.tgz"

cwd=$(pwd)
install_path="$cwd/mongo_install"
data_path="$cwd/mongo_data"
log_path="$cwd/mongo_log"

if [ -f "$script_dir/install_mongodb.cfg" ]
then
  # Not the most secure way
  `source  "$script_dir/install_mongodb.cfg"`
  if [ ! -z $mongo_download_url ]
  then
    download_url=$mongo_download_url
  fi
  if [ ! -z $mongo_install_path ]
  then
    install_path=$mongo_install_path
  fi
  if [ ! -z $mongo_install_path ]
  then
    data_path=$mongo_data_path
  fi
  if [ ! -z $mongo_log_path ]
  then
    log_path=$mongo_log_path
  fi
fi


printf "##Downloading source from $download_url##\n"
wget $download_url

filename="${download_url##*/}"
dir_name="${filename%.*}"

tar -xvzf $filename

untar_dir=`echo */`

mv $cwd/$untar_dir $install_path

printf "##Creating required data and log dirs##\n"
mkdir -p $data_path
mkdir -p $log_path


printf "\n##Updating .bashrc##\n"

printf "\n\n#Entries added by install_mongodb script - START" >> ~/.bashrc
printf "\nexport PATH=$install_path/bin:\$PATH" >> ~/.bashrc
printf "\nalias start_mongo='mongod --dbpath=$data_path --fork --logpath $log_path/mongo.log &'" >> ~/.bashrc
printf "\nalias stop_mongo='mongod --dbpath=$data_path --shutdown'" >> ~/.bashrc
printf "\n#Entries added by install_mongodb script - STOP\n" >> ~/.bashrc

export PATH=$install_path/bin:\$PATH
printf "\n##Starting mongodb....\n"
mongod --dbpath=$data_path --fork --logpath $log_path/mongo.log &
/bin/sleep 5

if [ $# -gt 0 ]
then
    if [ "$1" == "setup" ]
    then
        printf "\n##Setting up admin user and mongo_test collection\n"
        mongo admin --eval 'db.createUser( {user: "mongodbadmin", pwd: "V3admin", roles: [ { role: "userAdminAnyDatabase", db: "admin" }]});'
        mongo mongo_test -u mongodbadmin -p V3admin --authenticationDatabase admin --eval 'db.createUser( {user: "test", pwd: "test", roles: [ { role: "readWrite", db: "mongo_test" }]});'
    fi
fi

printf "\n\n##Installed and started mongodb.
Please verify the contents added to  your ~/.bashrc file and then source ~/.bashrc.
Use the command start_mongo to start and stop_mongo to stop mongodb##\n"



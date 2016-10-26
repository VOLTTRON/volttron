#!/bin/bash


#Script to install mongodb from source. reads install_mongodb.cfg from the
#same directory as this script
script_dir=$( cd $(dirname $0) ; pwd -P )
download_url="https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-3.2.4.tgz"
cwd=$(pwd)
install_path="$cwd/mongo_install"
config_file="$script_dir/default_mongodb.conf"
setup_test=0

function usage {
      printf "\nUsage:"
      printf "\n   install_mongodb.sh [-h] [-d download_url] [-i install_dir] [-c config_file] [-s]"
      printf "\nOptional arguments:"
      printf "\n   -s setup admin user and test collection after install and startup"
      printf "\n   -d download url. defaults to https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-3.2.4.tgz"
      printf "\n   -i install_dir. defaults to current_dir/mongo_install"
      printf "\n   -c config file to be used for mongodb startup. Defaults to default_mongodb.conf in the same directory as this script"
      printf "\n      Any datapath mentioned in the config file should already exist and should have write access to the current user"
      printf "\n   -h print this help message\n"

}

while getopts ":d:i:c:hs" opt; do
  case $opt in
    d)
      $download_url=$OPTARG
      ;;
    s)
      setup_test=1
      ;;
    i)
      install_path=$OPTARG
      parent_dir="$(dirname "$install_path")"
      if [ ! -d $parent_dir ]
      then
       printf "\nParent directory of given install path not a valid\n"
       exit 1
      else
        if [ -d $install_path ] || [ -f $install_path ]
        then
          printf "$install_path already exists\n"
          exit 1
        fi
      fi
      printf "\n##Using install dir $install_path\n"
      ;;
    c)
      config_file=$OPTARG
      if [ ! -f $config_file ]
      then
       printf "\nInvalid config file $config_file\n"
       exit 1
      fi
      printf "\n##Using config file $config_file"
      ;;
    h)
      usage
      exit 0
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      usage
      exit 1
      ;;
    :)
      echo "Option -$OPTARG requires an argument." >&2
      usage
      exit 1
      ;;
  esac
done

if [ -d $install_path ] || [ -f $install_path ]
then
  printf "$install_path already exists\n"
  exit 1
fi

printf "\n##Downloading source from $download_url##\n"
mkdir download_dir #create a clean temp_1 directory for our use and untar in it
cd download_dir
wget $download_url
filename="${download_url##*/}"
tar -xvzf $filename
untar_dir=`echo */`

printf "\n##Installing to $install_path\n"

#install_path=$(echo $install_path | sed 's:/*$::')
#untar_dir=$(echo $untar_dir | sed 's:/*$::')

mv $cwd/download_dir/$untar_dir $install_path
cp $config_file $install_path/mongo_config.cfg

printf "\n##Updating .bashrc##\n"

printf "\n#Entries added by install_mongodb script - START" >> ~/.bashrc
printf "\nexport PATH=$install_path/bin:\$PATH" >> ~/.bashrc
printf "\nalias start_mongo='mongod --config $install_path/mongo_config.cfg &'" >> ~/.bashrc
printf "\nalias stop_mongo='mongod --config $install_path/mongo_config.cfg --shutdown'" >> ~/.bashrc
printf "\n#Entries added by install_mongodb script - STOP\n" >> ~/.bashrc

echo "test"
printf "\n##Starting mongodb....\n"
export PATH=$install_path/bin/:\$PATH
$install_path/bin/mongod --config $config_file &
/bin/sleep 5


if [ "$setup_test" == 1 ]
then
    printf "\n##Setting up admin user and mongo_test collection\n"
    mongo admin --eval 'db.createUser( {user: "mongodbadmin", pwd: "V3admin", roles: [ { role: "userAdminAnyDatabase", db: "admin" }]});'
    mongo mongo_test -u mongodbadmin -p V3admin --authenticationDatabase admin --eval 'db.createUser( {user: "test", pwd: "test", roles: [ { role: "readWrite", db: "mongo_test" }]});'
fi

printf "\n\n##Installed and started mongodb.
Please verify the contents added to  your ~/.bashrc file and then source ~/.bashrc.
Use the command start_mongo to start and stop_mongo to stop mongodb##\n"
#! /bin/bash                                                                                       

 # Utility script for installing mysql, mongodb, and postgresql on Ubuntu 22.04 and creates test data base and test
 # db user for testing volttron agents that use these databases. Installs databases on a /databases
 # folder and assumes the unix user running VOLTTRON is "volttron"
 # You can use this as a reference, update database versions and user name as needed to install database environment for
 # testing volttron agents
 # To run provide execute permissions and pass one or more database names as input
 # For example
 # ./install-dbs-ubuntu-2204.sh mongodb mysql postgresql
 # ./install-dbs-ubuntu-2204.sh mongodb
 # ./install-dbs-ubuntu-2204.sh mysql
                                                                                                   
function install_mongodb(){                                                                        
  mkdir -p /databases/mongodb                                                                                
  cd /databases/mongodb                                                                                    
  sudo apt-get install -y libcurl4 libgssapi-krb5-2 libldap-2.5-0 libwrap0 libsasl2-2 libsasl2-modules libsasl2-modules-gssapi-mit openssl liblzma5
  wget https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2204-7.0.1.tgz
  tar -xvzf mongodb-linux-x86_64-ubuntu2204-7.0.1.tgz                                             
  ln -s mongodb-linux-x86_64-ubuntu2204-7.0.1 mongodb                                             
  mkdir data                                                                                       
  mkdir log  
  chown -R volttron /databases/mongodb   
  export PATH=$PATH:/databases/mongodb/mongodb/bin  
  echo 'export PATH=$PATH:/databases/mongodb/mongodb/bin' >> /home/volttron/.bashrc                
  echo "alias start_mongo='mongod --dbpath /databases/mongodb/data --logpath /databases/mongodb/log/mongod.log --fork'" >> /home/volttron/.bash_aliases    
  echo "alias stop_mongo='mongod --dbpath /databases/mongodb/data --logpath /databases/mongodb/log/mongod.log  --shutdown'" >> /home/volttron/.bash_aliases 
  su volttron -c "/databases/mongodb/mongodb/bin/mongod --dbpath /databases/mongodb/data --logpath /databases/mongodb/log/mongod.log --fork"
  wget https://downloads.mongodb.com/compass/mongosh-1.10.6-linux-x64-openssl3.tgz
  tar -xvzf mongosh-1.10.6-linux-x64-openssl3.tgz
  mv mongosh-1.10.6-linux-x64-openssl3/bin/* /databases/mongodb/mongodb/bin
  chmod a+x /databases/mongodb/mongodb/bin/mongosh 
  mongosh admin --eval 'db.createUser( {user: "admin", pwd: "volttron", roles: [ { role: "userAdminAnyDatabase", db: "admin" }]});'
  mongosh test_historian -u admin -p volttron --authenticationDatabase admin --eval 'db.createUser( {user: "historian", pwd: "historian", roles: [ { role: "readWrite", db: "test_historian" }]});'
  su volttron -c "/databases/mongodb/mongodb/bin/mongod --dbpath /databases/mongodb/data --logpath /databases/mongodb/log/mongod.log --shutdown"
} 


function install_mysql(){
  apt-get install -y libaio1 libncurses5 libnuma1
  mkdir -p /databases/mysql
  cd /databases/mysql
  wget https://downloads.mysql.com/archives/get/p/23/file/mysql-8.0.25-linux-glibc2.12-x86_64.tar.xz
  tar -xvf mysql-8.0.25-linux-glibc2.12-x86_64.tar.xz
  ln -s mysql-8.0.25-linux-glibc2.12-x86_64 mysql
  groupadd mysql
  useradd -r -g mysql -s /bin/false mysql
  mkdir mysql-files data etc log 
  chmod 750 mysql-files data etc log
  echo "[mysqld]" > etc/my.cnf
  echo "basedir=/databases/mysql/mysql" >> etc/my.cnf
  echo "datadir=/databases/mysql/data" >> etc/my.cnf
  echo "log-error=/databases/mysql/log/mysql.err" >> etc/my.cnf
  cd /databases/mysql
  cp mysql/support-files/mysql.server mysql/bin
  chown -R mysql:mysql /databases/mysql
  export PATH=/databases/mysql/mysql/bin:$PATH
  echo 'export PATH=/databases/mysql/mysql/bin:$PATH' >> /root/.bashrc
  echo 'export PATH=/databases/mysql/mysql/bin:$PATH' >> /home/volttron/.bashrc
  echo "alias start_mysql='sudo /databases/mysql/mysql/bin/mysql.server start'" >> /home/volttron/.bash_aliases
  echo "alias stop_mysql='sudo /databases/mysql/mysql/bin/mysql.server stop'" >> /home/volttron/.bash_aliases
  mysqld --defaults-file=/databases/mysql/etc/my.cnf --initialize-insecure --user=mysql
  sed -i 's/^basedir=/basedir=\/databases\/mysql\/mysql/' /databases/mysql/mysql/bin/mysql.server
  sed -i 's/^datadir=/datadir=\/databases\/mysql\/data/' /databases/mysql/mysql/bin/mysql.server
  mysql.server start
  mysql -u root -e "CREATE DATABASE test_historian;"
  mysql -u root -e "CREATE USER 'historian'@'localhost' IDENTIFIED BY 'historian';"
  mysql -u root -e "GRANT SELECT, INSERT, DELETE, CREATE, INDEX, UPDATE, DROP ON test_historian.* TO 'historian'@'localhost';"
  mysql -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY 'volttron';"
  mysql.server stop
}


function install_postgresql(){
  apt-get install -y libreadline8 libreadline-dev zlib1g-dev
  mkdir -p /databases/postgresql
  cd /databases/postgresql
  wget https://ftp.postgresql.org/pub/source/v10.16/postgresql-10.16.tar.gz
  tar -xvzf   postgresql-10.16.tar.gz
  ln -s postgresql-10.16 postgresql_source
  cd postgresql_source
  ./configure --prefix=/databases/postgresql/pgsql 
  make
  make install
  echo 'export LD_LIBRARY_PATH=/databases/postgresql/pgsql/lib' >> /home/volttron/.bashrc
  export LD_LIBRARY_PATH=/databases/postgresql/pgsql/lib
  echo 'export PATH=/databases/postgresql/pgsql/bin:$PATH' >> /home/volttron/.bashrc
  export PATH=/databases/postgresql/pgsql/bin:$PATH
  export LD_LIBRARY_PATH=/databases/postgresql/pgsql/lib
  ln -s /databases/postgresql/pgsql/lib/libpq.so.5 /usr/lib/libpq.so.5
  adduser --disabled-password  --gecos "" postgres
  mkdir /databases/postgresql/pgsql/data
  chown -R postgres /databases/postgresql
  su postgres -c "/databases/postgresql/pgsql/bin/initdb -D /databases/postgresql/pgsql/data"
  echo "alias start_postgres='sudo su postgres -c \"/databases/postgresql/pgsql/bin/pg_ctl -D /databases/postgresql/pgsql/data -l /databases/postgresql/logfile start\"'" >> /home/volttron/.bash_aliases
  echo "alias stop_postgres='sudo su postgres -c \"/databases/postgresql/pgsql/bin/pg_ctl -D /databases/postgresql/pgsql/data -l /databases/postgresql/logfile stop\"'" >> /home/volttron/.bash_aliases
  sudo su postgres -c "/databases/postgresql/pgsql/bin/pg_ctl -D /databases/postgresql/pgsql/data -l /databases/postgresql/logfile start"
  psql -U postgres -c 'CREATE DATABASE test_historian;'
  psql -U postgres -c "CREATE USER historian with encrypted password 'historian';"
  psql -U postgres -c "GRANT ALL PRIVILEGES on database test_historian to historian;"
  sudo su postgres -c "/databases/postgresql/pgsql/bin/pg_ctl -D /databases/postgresql/pgsql/data -l /databases/postgresql/logfile stop"
}

echo "Configured to install dbs: $@"
v=( "$@" )
for i in ${v[@]}
do
  echo "Calling install_$i"
  install_$i
done

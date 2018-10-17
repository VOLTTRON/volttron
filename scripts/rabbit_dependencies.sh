sudo pwd
DIST="$1"
list=( artful bionic jessie precise rtful sid stretch trusty weezy xenial yakkety zesty ) 

FOUND=0
for item in ${list[@]}; do
    if [ "$DIST" == "$item" ]; then
	FOUND=1
	break
    fi
done

if [ "$FOUND" != "1" ]; then
    echo "Invalid distribution found please pass one of these to the script"
    echo ${list[@]}
    echo
    exit 0
fi

echo "installing ERLANG"
sudo apt-get install apt-transport-https libwxbase3.0-0v5 libwxgtk3.0-0v5 libsctp1  build-essential python-dev openssl libssl-dev libevent-dev git
sudo apt-get purge -yf erlang*

wget -O - 'https://dl.bintray.com/rabbitmq/Keys/rabbitmq-release-signing-key.asc' | sudo apt-key add -

if [ ! -f "/etc/apt/sources.list.d/bintray.erlang.list" ]; then
  echo "deb https://dl.bintray.com/rabbitmq/debian $DIST erlang-21.x"|sudo tee --append /etc/apt/sources.list.d/bintray.erlang.list
fi
sudo apt-get update
sudo apt-get install -yf
sudo apt-get install -y erlang-base erlang-diameter erlang-eldap erlang-ssl erlang-crypto erlang-asn1 erlang-public-key
sudo apt-get install -y erlang-nox

echo "Finished installing dependencies for rabbitmq"

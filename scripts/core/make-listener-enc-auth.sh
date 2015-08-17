export SOURCE=examples/ListenerAgent/ 
export CONFIG=examples/ListenerAgent/config 
export TAG=listener 

#Public portion of the keypair command. Should have credentials in auth.json
PUBLIC_KEY=SomeKey

#Secret portion of the keypair
SECRET_KEY=SomeKey
#Public server key
CURVE_KEY=SomeKey
SOCKET=tcp://IPADDR:PORT

export VIP_ADDRESS="$SOCKET?serverkey=$CURVE_KEY&publickey=$PUBLIC_KEY&secretkey=$SECRET_KEY"

./scripts/core/make-agent.sh 

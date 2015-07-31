The volttron central agent allows the control of different volttron platforms
through the  platform agent that are registered.  The registration of
platforms can be initiated either from the platform agent side or from volttron
central requesting to manage a specified platform agent.  Once a platform
agent is registered the allowed operations are start, stop, install, and run
methods on the registered platform's agents.

Configuration
-----------------------
The agentid does not have to be unique.  It is what will be used
as a human readable name on volttron central.  If it is not set the
default 'volttron central' will be used.  The default config file is pasted below.
in the following.
{
    "agentid": "volttron central",
    "vip_identity": "volttron.central",
    "log_file": "~/.volttron/volttron.log",
    "server" : {
        "host": "127.0.0.1",
        "port": 8080,
        "debug": "False"
    },
    "users" : {
        "reader" : {
            "password" : "2d7349c51a3914cd6f5dc28e23c417ace074400d7c3e176bcf5da72fdbeb6ce7ed767ca00c6c1fb754b8df5114fc0b903960e7f3befe3a338d4a640c05dfaf2d",
            "groups" : [
                "reader"
            ]
        },
        "writer" : {
            "password" : "f7c31a682a838bbe0957cfa0bb060daff83c488fa5646eb541d334f241418af3611ff621b5a1b0d327f1ee80da25e04099376d3bc533a72d2280964b4fab2a32",
            "groups" : [
                "writer"
            ]
        },
        "admin" : {
            "password" : "c7ad44cbad762a5da0a452f9e854fdc1e0e7a52a38015f23f3eab1d80b931dd472634dfac71cd34ebc35d16ab7fb8a90c81f975113d6c7538dc69dd8de9077ec",
            "groups" : [
                "admin"
            ]
        },
        "dorothy" : {
            "password" : "cf1b67402d648f51ef6ff8805736d588ca07cbf018a5fba404d28532d839a1c046bfcd31558dff658678b3112502f4da9494f7a655c3bdc0e4b0db3a5577b298",
            "groups" : [
                "reader, writer"
            ]
        }
    }
}

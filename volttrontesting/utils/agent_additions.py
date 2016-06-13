def add_vc_to_instance(wrapper):

    config = {
        # The agentid is used during display on the VOLTTRON central platform
        # it does not need to be unique.
        "agentid": "Volttron Central",

        # By default the webroot will be relative to the installation directory
        # of the agent when it is installed.  One can override this by specifying
        # the root directory here.
        # "webroot": "path/to/webroot",

        # Authentication for users is handled through a naive password algorithm
        # import hashlib
        # hashlib.sha512(password).hexdigest() where password is the plain text password.
        "users": {
            "reader": {
                "password": "2d7349c51a3914cd6f5dc28e23c417ace074400d7c3e176bcf5da72fdbeb6ce7ed767ca00c6c1fb754b8df5114fc0b903960e7f3befe3a338d4a640c05dfaf2d",
                "groups": [
                    "reader"
                ]
            },
            "admin": {
                "password": "c7ad44cbad762a5da0a452f9e854fdc1e0e7a52a38015f23f3eab1d80b931dd472634dfac71cd34ebc35d16ab7fb8a90c81f975113d6c7538dc69dd8de9077ec",
                "groups": [
                    "admin"
                ]
            },
            "dorothy": {
                "password": "cf1b67402d648f51ef6ff8805736d588ca07cbf018a5fba404d28532d839a1c046bfcd31558dff658678b3112502f4da9494f7a655c3bdc0e4b0db3a5577b298",
                "groups": [
                    "reader, writer"
                ]
            }
        }
    }

    agent_uuid = wrapper.install_agent(config_file=config,
                                       agent_dir="services/core/VolttronCentral")
    return agent_uuid
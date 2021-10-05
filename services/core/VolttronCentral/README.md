# VOLTTRON Central Agent

The VOLTTRON Central agent allows the control of remote VOLTTRON
platforms through the registered platform agents. The registration of
platforms can be initiated from a remote platform agent. Once a platform
agent is registered the allowed operations are start, stop, install, and
run methods on the registered platform\'s agents.

# Configuration

The agentid does not have to be unique. It is what will be used as a
human readable name on volttron central. If it is not set the default
\'volttron central\' will be used. The default config file is pasted
below. in the following.

    # By default the webroot will be relative to the installation directory
    # of the agent when it is installed.  One can override this by specifying
    # the root directory here.
    # "webroot": "path/to/webroot",

# Security Considerations

When deploying any web agent, including VOLTTRON Central, it is important to consider security.
Please refer to the documentation for :ref:`Security Considerations of Deployment <Secure-Deployment-Considerations>`. 
In particular, it would be recommended to consider the use of a reverse proxy.


# TODO create secure volttron_fixture

def test_agent_install_default(volttron_instance):
    """

    :param volttron_instance:
    :return:
    """
    # TODO install listener, check agents installed
    # TODO check /etc/passwd and /etc/group to make sure no users/groups exist
    # for the test instance
    # TODO try to start the agent, make sure it started
    # TODO check /etc/passwd and /etc/group to make sure no users/groups exist
    # for the test instance
    # TODO test agent removal
    # TODO adding and removing multiple copies of an agent

def test_agent_install_secure():
    # TODO install security agent, check agents installed
    # TODO check /etc/passwd /etc/group to make sure users/groups exist for the
    # test instance
    # TODO start security agent
    # TODO check /etc/passwd and /etc/group to make sure users/groups exist for
    # the test instance
    # TODO test agent removal
    # TODO check /etc/passwd and /etc/group to make sure no users/groups exist
    # for the test instance
    # TODO install agent, then delete agent user
    # TODO start security agent, check to make sure users/groups exist
    # TODO remove it again and check that it is successfully removed
    # TODO repeat the previous, deleting group as well
    # TODO adding and removing multiple copies of an agent



# TODO test agent directory permissions

# test agent user sudo perms

# TODO test volttron user add/delete user

# TODO test volttron user add/delete group

# TODO test volttron user add/delete other

# TODO test remove agent secure

# TODO instance names?

# TODO group names?
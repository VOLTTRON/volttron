#RMQAuthorization(BaseAuthorization)
#RMQAuthentication(BaseAuthentication)

@RPC.export
@RPC.allow(capabilities="allow_auth_modifications")
def get_pending_csrs(self):
    """RPC method

    Returns a list of pending CSRs.
    This method provides RPC access to the Certs class's
    get_pending_csr_requests method.
    This method is only applicable for web-enabled, RMQ instances.

    :rtype: list
    """
    if self._certs:
        csrs = [c for c in self._certs.get_pending_csr_requests()]
        return csrs
    else:
        return []

@RPC.export
@RPC.allow(capabilities="allow_auth_modifications")
def get_pending_csr_status(self, common_name):
    """RPC method

    Returns the status of a pending CSRs.
    This method provides RPC access to the Certs class's get_csr_status
    method.
    This method is only applicable for web-enabled, RMQ instances.
    Currently, this method is only used by admin_endpoints.

    :param common_name: Common name for CSR
    :type common_name: str
    :rtype: str
    """
    if self._certs:
        return self._certs.get_csr_status(common_name)
    else:
        return ""

@RPC.export
@RPC.allow(capabilities="allow_auth_modifications")
def get_pending_csr_cert(self, common_name):
    """RPC method

    Returns the cert of a pending CSRs.
    This method provides RPC access to the Certs class's
    get_cert_from_csr method.
    This method is only applicable for web-enabled, RMQ instances.
    Currently, this method is only used by admin_endpoints.

    :param common_name: Common name for CSR
    :type common_name: str
    :rtype: str
    """
    if self._certs:
        return self._certs.get_cert_from_csr(common_name).decode("utf-8")
    else:
        return ""

@RPC.export
@RPC.allow(capabilities="allow_auth_modifications")
def get_all_pending_csr_subjects(self):
    """RPC method

    Returns a list of all certs subjects.
    This method provides RPC access to the Certs class's
    get_all_cert_subjects method.
    This method is only applicable for web-enabled, RMQ instances.
    Currently, this method is only used by admin_endpoints.

    :rtype: list
    """
    if self._certs:
        return self._certs.get_all_cert_subjects()
    else:
        return []

def _load_protected_topics_for_rmq(self):
    try:
        write_protect = self._protected_topics["write-protect"]
    except KeyError:
        write_protect = []

    topics = ProtectedPubSubTopics()
    try:
        for entry in write_protect:
            topics.add(entry["topic"], entry["capabilities"])
    except KeyError:
        _log.exception("invalid format for protected topics ")
    else:
        self._protected_topics_for_rmq = topics

def _check_topic_rules(self, sender, **kwargs):
    delay = 0.05
    self.core.spawn_later(delay, self._check_rmq_topic_permissions)

def _check_rmq_topic_permissions(self):
    """
    Go through the topic permissions for each agent based on the
    protected topic setting.
    Update the permissions for the agent/user based on the latest
    configuration

    :return:
    """
    return
    # Get agent to capabilities mapping
    user_to_caps = self.get_user_to_capabilities()
    # Get topics to capabilities mapping
    topic_to_caps = self._protected_topics_for_rmq.get_topic_caps()  #
    # topic to caps

    peers = self.vip.peerlist().get(timeout=5)
    # _log.debug("USER TO CAPS: {0}, TOPICS TO CAPS: {1}, {2}".format(
    # user_to_caps,
    # topic_to_caps,
    # self._user_to_permissions))
    if not user_to_caps or not topic_to_caps:
        # clear all old permission rules
        for peer in peers:
            self._user_to_permissions[peer].clear()
    else:
        for topic, caps_for_topic in topic_to_caps.items():
            for user in user_to_caps:
                try:
                    caps_for_user = user_to_caps[user]
                    common_caps = list(
                        set(caps_for_user).intersection(caps_for_topic)
                    )
                    if common_caps:
                        self._user_to_permissions[user].add(topic)
                    else:
                        try:
                            self._user_to_permissions[user].remove(topic)
                        except KeyError:
                            if not self._user_to_permissions[user]:
                                self._user_to_permissions[user] = set()
                except KeyError:
                    try:
                        self._user_to_permissions[user].remove(topic)
                    except KeyError:
                        if not self._user_to_permissions[user]:
                            self._user_to_permissions[user] = set()

    all = set()
    for user in user_to_caps:
        all.update(self._user_to_permissions[user])

    # Set topic permissions now
    for peer in peers:
        not_allowed = all.difference(self._user_to_permissions[peer])
        self._update_topic_permission_tokens(peer, not_allowed)
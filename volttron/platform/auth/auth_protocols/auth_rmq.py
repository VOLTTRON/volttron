# RMQAuthorization(BaseAuthorization)
import os
import ssl
import re
import logging
import grequests
from collections import defaultdict
from urllib.parse import urlparse, urlsplit
from dataclasses import dataclass
from volttron.platform.auth import certs
from volttron.platform.auth.auth_protocols import *
from volttron.platform.parameters import Parameters
from volttron.utils.rmq_config_params import RMQConfig
from volttron.utils.rmq_mgmt import RabbitMQMgmt
from volttron.platform import jsonapi
from volttron.platform.agent.utils import get_fq_identity, get_platform_instance_name
from volttron.platform.messaging.health import STATUS_BAD
from volttron.platform import get_home

from volttron.platform import is_rabbitmq_available

if is_rabbitmq_available():
    import pika

_log = logging.getLogger(__name__)


@dataclass
class RMQClientParameters(Parameters):
    rmq_user: str = None
    pwd: str = None
    host: str = None
    port: int = None
    vhost: str = None
    connection_params: pika.ConnectionParameters = None
    url_address: str = None
    certs_dict: dict = None


class RMQConnectionAPI:
    """
    Utility class to hold all connection parameters and connection creation methods.
    """
    def __init__(self, rmq_user=None,
                 pwd=None,
                 host=None,
                 port=None,
                 vhost=None,
                 heartbeat=20,
                 retry_attempt=30,
                 retry_delay=2,
                 ssl_auth=True,
                 certs_dict=None,
                 url_address=None) -> None:
        self.rmq_mgmt = RabbitMQMgmt()
        rmq_user = rmq_user if rmq_user else self.rmq_mgmt.rmq_config.admin_user
        pwd = pwd if pwd else self.rmq_mgmt.rmq_config.admin_pwd
        host = host if host else self.rmq_mgmt.rmq_config.hostname
        if port:
            port = port
        else:
            port = self.rmq_mgmt.rmq_config.amqp_port_ssl if self.rmq_mgmt.rmq_config.is_ssl else self.rmq_mgmt.rmq_config.amqp_port

        vhost = vhost if vhost else self.rmq_mgmt.rmq_config.virtual_host
        self.params = RMQClientParameters(
            rmq_user=rmq_user,
            pwd=pwd,
            host=host,
            port=port,
            vhost=vhost,
            connection_params=pika.ConnectionParameters(
                host=host,
                port=port,
                virtual_host=vhost,
                connection_attempts=retry_attempt,
                retry_delay=retry_delay,
                heartbeat=heartbeat,
                credentials=pika.credentials.PlainCredentials(
                    rmq_user, rmq_user)
            ),
            url_address=url_address if url_address else f"amqp://{rmq_user}:{pwd}@{host}:{port}/{vhost}",
            certs_dict=certs_dict
        )
        self.ssl_auth = ssl_auth

    def build_connection_param(self):
        if self.ssl_auth:
            authenticated_params, _ = RMQClientAuthentication(self.params).create_authentication_parameters()
            return authenticated_params
        else:
            return self.params.connection_params

    def build_router_connection(self, identity, instance_name):
        """
        Check if RabbitMQ user and certs exists for the router, if not
        create a new one. Add access control/permissions if necessary.
        Return connection parameters.
        :param identity: Identity of agent
        :param instance_name: name of the volttron instance
        :return:
        """
        self.params.rmq_user = instance_name + '.' + identity
        permissions = dict(configure=".*", read=".*", write=".*")

        if self.ssl_auth:
            self.rmq_mgmt.rmq_config.crts.create_signed_cert_files(self.params.rmq_user, overwrite=False)

        self.rmq_mgmt.create_user_with_permissions(self.params.rmq_user, permissions, ssl_auth=self.ssl_auth)
        param = self.build_connection_param()
        return param

    def build_remote_connection_param(self, cert_dir=None, retry_attempt=30, retry_delay=2):
        """
        Build Pika Connection parameters for remote connection
        :param cert_dir: certs directory
        :param retry_delay: pika connection parameter - delay between connection retry
        :param retry_attempt: pika connection parameter - number of connection retry attempts
        :return: instance of pika.ConnectionParameters
        """
        from urllib import parse

        parsed_addr = parse.urlparse(self.params.url_address)
        _, virtual_host = parsed_addr.path.split('/')

        try:
            if self.ssl_auth:
                certfile = self.rmq_mgmt.certs.cert_file(self.params.rmq_user, True)
                if cert_dir:
                    # remote cert file for agents will be in agent-data/remote-certs dir
                    certfile = os.path.join(cert_dir, os.path.basename(certfile))
                _log.info("build_remote_connection_param: {}".format(certfile))
                metafile = certfile[:-4] + ".json"
                metadata = jsonapi.loads(open(metafile).read())
                local_keyfile = metadata['local_keyname']
                ca_file = self.rmq_mgmt.certs.cert_file(metadata['remote_ca_name'], True)
                if cert_dir:
                    ca_file = os.path.join(cert_dir, os.path.basename(ca_file))
                context = ssl.create_default_context(cafile=ca_file)
                context.load_cert_chain(certfile,
                                        self.rmq_mgmt.certs.private_key_file(local_keyfile))

                ssl_options = pika.SSLOptions(context, parsed_addr.hostname)
                self.params.connection_params = pika.ConnectionParameters(
                    host=parsed_addr.hostname,
                    port=parsed_addr.port,
                    virtual_host=virtual_host,
                    connection_attempts=retry_attempt,
                    retry_delay=retry_delay,
                    ssl_options=ssl_options,
                    credentials=pika.credentials.ExternalCredentials())

        except KeyError:
            return None
        return self.params.connection_params

    def build_agent_connection(self, identity, instance_name):
        """
        Check if RabbitMQ user and certs exists for this agent, if not
        create a new one. Add access control/permissions if necessary.
        Return connection parameters.
        :param identity: Identity of agent
        :param instance_name: instance name of the platform
        :param is_ssl: Flag to indicate if SSL connection or not
        :return: Return connection parameters
        """

        self.params.rmq_user = get_fq_identity(identity, instance_name)
        permissions = self.rmq_mgmt.get_default_permissions(self.params.rmq_user)

        if self.ssl_auth:
            # This could fail with permission error when running in secure mode
            # and agent was installed when volttron was running on ZMQ instance
            # and then switched to RMQ instance. In that case
            # vctl certs create-ssl-keypair should be used to create a cert/key pair
            # and then agents should be started.
            try:
                c, k = self.rmq_mgmt.rmq_config.crts.create_signed_cert_files(self.params.rmq_user, overwrite=False)
            except Exception as e:
                _log.error("Exception creating certs. {}".format(e))
                raise RuntimeError(e)
        param = None

        try:
            _, _, admin_user = certs.Certs.get_admin_cert_names(self.rmq_mgmt.rmq_config.instance_name)
            if os.access(self.rmq_mgmt.rmq_config.crts.private_key_file(admin_user), os.R_OK):
                # this must be called from service agents. Create rmq user with permissions
                # for installed agent this would be done by aip at start of agent
                self.rmq_mgmt.create_user_with_permissions(self.params.rmq_user, permissions, ssl_auth=self.ssl_auth)
            param = self.build_connection_param()
        except AttributeError:
            _log.error("Unable to create RabbitMQ user for the agent. Check if RabbitMQ broker is running")

        return param

    def build_local_plugin_connection(self):
        config_access = "{user}|{user}.pubsub.*|{user}.zmq.*|amq.*".format(
            user=self.params.rmq_user)
        read_access = "volttron|{}".format(config_access)
        write_access = "volttron|{}".format(config_access)
        permissions = dict(configure=config_access, read=read_access,
                           write=write_access)

        self.rmq_mgmt.create_user_with_permissions(self.params.rmq_user, permissions)
        if self.ssl_auth:
            self.rmq_mgmt.rmq_config.crts.create_signed_cert_files(self.params.rmq_user, overwrite=False)
        _, self.params.url_address = RMQClientAuthentication(self.params).create_authentication_parameters()
        return self.params.url_address

    def build_remote_plugin_connection(self):
        """
        Check if RabbitMQ user and certs exists for this agent, if not
        create a new one. Add access control/permissions if necessary.
        Return connection parameters.
        :param identity: Identity of agent
        :param instance_name: instance name of the platform
        :param host: hostname
        :param port: amqp/amqps port
        :param vhost: virtual host
        :param is_ssl: Flag to indicate if SSL connection or not
        :return: Return connection uri
        """
        if self.ssl_auth and self.params.certs_dict is not None:
            client_auth = RMQClientAuthentication(self.params)
            client_auth.params.connection_params = None
            _, self.params.url_address = client_auth.create_authentication_parameters()
        else:
            # should not come here. federation and shovel setup create certs before this method is called.
            # ssl_auth should be true certs_dict should have ca, public and private key file path
            raise Exception("For RMQ remote connection bost ssl certificates are mandatory. ssl_auth should be "
                            "true and certs_dict should contain certificate details. passed values"
                            f"ssl_auth={self.ssl_auth} certs_dict={self.params.certs_dict}")
        return self.params.url_address


class RMQClientAuthentication(BaseAuthentication):
    def __init__(self, params: RMQClientParameters) -> None:
        super(RMQClientAuthentication, self).__init__()
        self.params = params
        self.rmq_mgmt = RabbitMQMgmt()

    def _get_values_from_addr(self):
        url = urlsplit(self.params.url_address)
        userpass, hostport = url.netloc.split("@")
        user, pwd = userpass.split(":")
        host, port = hostport.split(":")
        vhost = url.path.strip("/")
        return user, pwd, host, port, vhost

    # TODO: split into two methods. params.connection_params and url_address is never none so this always try to
    # create both connection param and url address
    def create_authentication_parameters(self):
        """
        Build Pika Connection parameters
        :return: Pika Connection, RMQ address
        """
        crt = self.rmq_mgmt.rmq_config.crts
        try:
            # Update RMQ connection params
            if self.params.connection_params:
                context = ssl.create_default_context(cafile=crt.cert_file(crt.trusted_ca_name))
                context.load_cert_chain(crt.cert_file(self.params.rmq_user),
                                        crt.private_key_file(self.params.rmq_user))

                ssl_options = pika.SSLOptions(context, self.rmq_mgmt.rmq_config.hostname)
                self.params.connection_params.ssl_options = ssl_options
                self.params.connection_params.credentials = pika.credentials.ExternalCredentials()
            # Update rmq address
            if self.params.url_address:
                user, pwd, host, port, vhost = self._get_values_from_addr()
                ssl_params = self.get_ssl_url_params(user, self.params.certs_dict)
                self.params.url_address = "amqps://{host}:{port}/{vhost}?" \
                                      "{ssl_params}&server_name_indication={host}".format(
                    host=host,
                    port=port,
                    vhost=vhost,
                    ssl_params=ssl_params)
        except KeyError:
            return None
        return self.params.connection_params, self.params.url_address

    def get_ssl_url_params(self, user=None, certs_dict=None):
        """
        Return SSL parameter string
        :return:
        """

        if not user:
            user = self.rmq_mgmt.rmq_config.admin_user
        if certs_dict is None:
            ca_file = self.rmq_mgmt.rmq_config.crts.cert_file(self.rmq_mgmt.rmq_config.crts.trusted_ca_name)
            cert_file = self.rmq_mgmt.rmq_config.crts.cert_file(user)
            key_file = self.rmq_mgmt.rmq_config.crts.private_key_file(user)
        else:
            ca_file = certs_dict['remote_ca']
            cert_file = certs_dict['public_cert']
            key_file = certs_dict['private_key']
        return "cacertfile={ca}&certfile={cert}&keyfile={key}" \
               "&verify=verify_peer&fail_if_no_peer_cert=true" \
               "&auth_mechanism=external".format(ca=ca_file,
                                                 cert=cert_file,
                                                 key=key_file)


class RMQServerAuthentication(BaseServerAuthentication):
    def __init__(self, auth_service) -> None:
        super(RMQServerAuthentication, self).__init__(auth_service=auth_service)
        from volttron.platform.vip.pubsubservice import ProtectedPubSubTopics
        self._protected_topics_for_rmq = ProtectedPubSubTopics()
        self.authorization = RMQAuthorization(self.auth_service)

    def setup_authentication(self):
        self.auth_service.vip.peerlist.onadd.connect(self.authorization.check_topic_rules)

    def handle_authentication(self, protected_topics):
        self.authorization.update_protected_topics(protected_topics)


# RMQAuthentication(BaseAuthentication)
class RMQAuthorization(BaseServerAuthorization):
    def __init__(self, auth_service) -> None:
        super().__init__(auth_service=auth_service)
        self._certs = certs.Certs()
        self._user_to_caps = None
        self._protected_topics_for_rmq = None

        def topics():
            return defaultdict(set)

        self._user_to_permissions = topics()

    def approve_authorization(self, user_id):
        try:
            self._certs.approve_csr(user_id)
            permissions = self.auth_service.core.rmq_mgmt.get_default_permissions(
                user_id
            )

            if "federation" in user_id:
                # federation needs more than
                # the current default permissions
                # TODO: Fix authorization in rabbitmq
                permissions = dict(configure=".*", read=".*", write=".*")
            self.auth_service.core.rmq_mgmt.create_user_with_permissions(
                user_id, permissions, True
            )
            _log.debug("Created cert and permissions for user: %r", user_id)
        except ValueError as err:
            _log.error(f"{err}")

    def deny_authorization(self, user_id):
        try:
            self._certs.deny_csr(user_id)
            _log.debug("Denied cert for user: {}".format(user_id))
        # Stores error message in case it is caused by an unexpected
        # failure
        except ValueError as err:
            _log.error(f"{err}")

    def delete_authorization(self, user_id):
        try:
            self._certs.delete_csr(user_id)
            _log.debug("Denied cert for user: {}".format(user_id))
        # Stores error message in case it is caused by an unexpected
        # failure
        except ValueError as err:
            _log.error(f"{err}")

    def update_user_capabilites(self, user_to_caps):
        self._user_to_caps = user_to_caps
        self._protected_topics_for_rmq = None
        self._check_rmq_topic_permissions()

    def load_protected_topics(self, protected_topics_data):
        protected_topics = super().load_protected_topics(protected_topics_data)
        self._load_rmq_protected_topics(protected_topics)
        return protected_topics

    def update_protected_topics(self, protected_topics):
        self._user_to_caps = None
        self._load_rmq_protected_topics(protected_topics)
        self._check_rmq_topic_permissions()

    def check_topic_rules(self, sender, **kwargs):
        delay = 0.05
        self.auth_service.core.spawn_later(delay, self._check_rmq_topic_permissions)

    def _check_rmq_topic_permissions(self):
        """
        TODO: When this is fixed, separate capabilities and topics to match zmq.
        Go through the topic permissions for each agent based on the
        protected topic setting.
        Update the permissions for the agent/user based on the latest
        configuration

        :return:
        """
        return
        # Get agent to capabilities mapping
        user_to_caps = self._user_to_caps
        # Get topics to capabilities mapping
        topic_to_caps = self._protected_topics_for_rmq.get_topic_caps()  #
        # topic to caps

        peers = self.auth_service.vip.peerlist().get(timeout=5)
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

    def _update_topic_permission_tokens(self, identity, not_allowed):
        """
        Make rules for read and write permission on topic (routing key)
        for an agent based on protected topics setting.

        :param identity: identity of the agent
        :return:
        """
        read_tokens = [
            "{instance}.{identity}".format(
                instance=self.auth_service.core.instance_name, identity=identity
            ),
            "__pubsub__.*",
        ]
        write_tokens = ["{instance}.*".format(instance=self.auth_service.core.instance_name)]

        if not not_allowed:
            write_tokens.append(
                "__pubsub__.{instance}.*".format(
                    instance=self.auth_service.core.instance_name
                )
            )
        else:
            not_allowed_string = "|".join(not_allowed)
            write_tokens.append(
                "__pubsub__.{instance}.".format(
                    instance=self.auth_service.core.instance_name
                )
                + "^(!({not_allow})).*$".format(not_allow=not_allowed_string)
            )
        current = self.auth_service.core.rmq_mgmt.get_topic_permissions_for_user(identity)
        # _log.debug("CURRENT for identity: {0}, {1}".format(identity,
        # current))
        if current and isinstance(current, list):
            current = current[0]
            dift = False
            read_allowed_str = "|".join(read_tokens)
            write_allowed_str = "|".join(write_tokens)
            if re.search(current["read"], read_allowed_str):
                dift = True
                current["read"] = read_allowed_str
            if re.search(current["write"], write_allowed_str):
                dift = True
                current["write"] = write_allowed_str
                # _log.debug("NEW {0}, DIFF: {1} ".format(current, dift))
                # if dift:
                #     set_topic_permissions_for_user(current, identity)
        else:
            current = dict()
            current["exchange"] = "volttron"
            current["read"] = "|".join(read_tokens)
            current["write"] = "|".join(write_tokens)
            # _log.debug("NEW {0}, New string ".format(current))
            # set_topic_permissions_for_user(current, identity)

    def _load_rmq_protected_topics(self, protected_topics):
        from volttron.platform.vip.pubsubservice import ProtectedPubSubTopics
        try:
            write_protect = protected_topics["write-protect"]
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

    # def get_pending_csr_cert(self, common_name):
    def get_authorization(self, user_id):
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
        return self._certs.get_cert_from_csr(user_id).decode("utf-8")

    # def get_pending_csr_status(self, common_name):
    def get_authorization_status(self, user_id):
        """RPC method

        Returns the status of a pending CSR.
        This method provides RPC access to the Certs class's get_csr_status
        method.
        This method is only applicable for web-enabled, RMQ instances.
        Currently, this method is only used by admin_endpoints.

        :param common_name: Common name for CSR
        :type common_name: str
        :rtype: str
        """
        return self._certs.get_csr_status(user_id)

    # def get_pending_csrs(self):
    def get_pending_authorizations(self):
        """RPC method

        Returns a list of pending CSRs.
        This method provides RPC access to the Certs class's
        get_pending_csr_requests method.
        This method is only applicable for web-enabled, RMQ instances.

        :rtype: list
        """
        csrs = [c for c in self._certs.get_pending_csr_requests() if c.get('status') == "PENDING"]
        return csrs

    def get_approved_authorizations(self):
        """RPC method

        Returns a list of all certs subjects.
        This method provides RPC access to the Certs class's
        get_all_cert_subjects method.
        This method is only applicable for web-enabled, RMQ instances.
        Currently, this method is only used by admin_endpoints.

        :rtype: list
        """
        csrs = [c for c in self._certs.get_pending_csr_requests() if c.get('status') == "APPROVED"]
        return csrs
        # return self._certs.get_all_cert_subjects()

    def get_denied_authorizations(self):
        csrs = [c for c in self._certs.get_pending_csr_requests() if c.get('status') == "DENIED"]
        return csrs


class RMQClientAuthorization(BaseClientAuthorization):
    def __init__(self, auth_service):
        super().__init__(auth_service)

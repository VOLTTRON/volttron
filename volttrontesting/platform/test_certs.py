import os
import tempfile
import shutil

import pytest
from volttron.platform.certs import Certs, Subject, CertError
from volttron.platform.agent.utils import get_platform_instance_name

INSTANCE_NAME = "VC"
PLATFORM_CONFIG = """
#host parameter is mandatory parameter. fully qualified domain name
host: mymachine.pnl.gov

# mandatory. certificate data used to create root ca certificate. Each volttron
# instance must have unique common-name for root ca certificate
certificate-data:
  country: 'US'
  state: 'Washington'
  location: 'Richland'
  organization: 'PNNL'
  organization-unit: 'VOLTTRON Team'
  # volttron_instance has to be replaced with actual instance name of the VOLTTRON
  common-name: 'volttron_instance_root_ca'
# certificate data could also point to existing public and private key files
# of a CA. In that case, use the below certificate-data parameters instead of
# the above. Note. public and private should be pem encoded and use rsa
#  encryption
#
#certificate-data:
#  ca-public-key: /path/to/ca/public/key/ca_pub.crt
#  ca-private-key: /path/to/ca/private/key/ca_private.pem


#
# optional parameters for single instance setup
#
virtual-host: 'volttron' #defaults to volttron

# use the below four port variables if using custom rabbitmq ports
# defaults to 5672
amqp-port: '5672'

# defaults to 5671
amqp-port-ssl: '5671'

# defaults to 15672
mgmt-port: '15672'

# defaults to 15671
mgmt-port-ssl: '15671'

# defaults to true
ssl: 'true'

# defaults to ~/rabbitmq_server/rabbbitmq_server-3.7.7
rmq-home: "~/rabbitmq_server/rabbitmq_server-3.7.7"
"""


@pytest.fixture(scope="function")
def temp_volttron_home(request):
    """
    Create a VOLTTRON_HOME and includes it in the test environment.
    Creates a volttron home, config, and platform_config.yml file
    for testing purposes.
    """
    dirpath = tempfile.mkdtemp()
    os.environ['VOLTTRON_HOME'] = dirpath
    with open(os.path.join(dirpath, "platform_config.yml"), 'w') as fp:
        fp.write(PLATFORM_CONFIG)

    with open(os.path.join(dirpath, "config"), "w") as fp:
        fp.write("[volttron]\n")
        fp.write("instance-name = {}\n".format(INSTANCE_NAME))
    yield dirpath
    shutil.rmtree(dirpath, ignore_errors=True)
    assert not os.path.exists(dirpath)


def test_certificate_directories(temp_volttron_home):
    certs = Certs()
    paths = (certs.certs_pending_dir, certs.private_dir, certs.cert_dir,
             certs.remote_cert_dir, certs.csr_pending_dir, certs.ca_db_dir)

    for p in paths:
        assert os.path.exists(p)


def test_create_root_ca(temp_volttron_home):
    certs = Certs()
    assert not certs.ca_exists()
    certs.create_root_ca()
    assert certs.ca_exists()


# def test_cadb_updated(temp_volttron_home):
#     certs = Certs()
#     certs.create_root_ca()
#     instance_name = get_platform_instance_name(False)
#     assert not os.path.exists(certs.ca_db_file(instance_name))
#     certs.create_instance_ca(instance_name)
#     assert os.path.exists(certs.ca_db_file(instance_name))
#
#
# def test_create_instance_ca(temp_volttron_home):
#     certs = Certs()
#     certs.create_root_ca()
#     instance_name = get_platform_instance_name(False)
#     assert instance_name == INSTANCE_NAME
#     assert not certs.cert_exists(instance_name)
#     certs.create_instance_ca(instance_name)
#     assert certs.cert_exists(instance_name)
#     assert certs.verify_cert(instance_name)

import gevent

from volttron.platform.keystore import KeyStore
from volttron.platform.messaging.health import STATUS_BAD, Status
from volttron.platform.vip.agent.utils import build_agent


test_subject = "Test subject1"
test_message = "this is a message that is sent via pubsub email"

message = dict(subject=test_subject, message=test_message)

ks = KeyStore()
agent = build_agent(identity="test.email.pubsub", enable_store=False)
agent.vip.pubsub.publish('pubsub', topic="platform/send_email", message=message)
# agent.vip.health.set_status(STATUS_BAD, "It's bad man really bad!")
agent.vip.health.send_alert("ALERT_KEY", Status.build(
    STATUS_BAD, "It's really bad again!"
))
gevent.sleep(5)
agent.core.stop()

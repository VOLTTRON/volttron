# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2019, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}



from collections import defaultdict

# Import the email modules we'll need
from email.mime.text import MIMEText
import logging
import socket

# Import smtplib for the actual sending function
import smtplib
import sys

import gevent
from volttron.platform.agent.utils import get_utc_seconds_from_epoch
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import topics
from volttron.platform.messaging.health import ALERT_KEY, STATUS_BAD, Status, \
    STATUS_GOOD
from volttron.platform.vip.agent import Agent

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '1.4.2'

"""
The `pyclass:EmailAgent` is responsible for sending emails for an instance.  It
has been written so that any agent on the instance can send emails through it
via the `pymethod:send_email` method or through the pubsub message bus (see
`topics.PLATFORM_SEND_EMAIL`).

A default configuration for this agent is as follows.

.. code-block:: json
    {
        "smtp_address": "smtp.foo.com",
        "from_address": "billy@foo.com",
        "to_addresses=to_address": ["ann@foo.com", "bob@gmail.com"],
        "allow_frequency_minutes": 10
    }

By default any alerts will be sent through this agent.  In addition all emails
will be published to the record/sent_email topic for a historian to be able
to capture that data.
"""


class EmailerAgent(Agent):

    def __init__(self, config_path, **kwargs):
        super(EmailerAgent, self).__init__(**kwargs)

        self.config = utils.load_config(config_path)
        self.smtp_address = self.config.get("smtp-address", None)
        self.from_address = self.config.get("from-address", None)
        self.to_address = self.config.get("to-addresses", None)
        self.smtp_port = self.config.get("smtp-port", None)
        self.smtp_username = self.config.get("smtp-username", None)
        self.smtp_password = self.config.get("smtp-password", None)
        self.smtp_tls = self.config.get("smtp-tls",None)
        self.allow_frequency_minutes = self.config.get("allow-frequency-minutes", 60)
        self._allow_frequency_seconds = self.allow_frequency_minutes * 60
        self.smtp_tls = self.config.get("smtp-tls",None)
        self.default_config = dict(smtp_address=self.smtp_address,
                                   from_address=self.from_address,
                                   to_addresses=self.to_address,
                                   smtp_port=self.smtp_port,
                                   smtp_username=self.smtp_username,
                                   smtp_password=self.smtp_password,
                                   smtp_tls = self.smtp_tls,
                                   allow_frequency_minutes=self.allow_frequency_minutes,
                                   alert_from_address=self.from_address,
                                   alert_to_addresses=self.to_address,
                                   send_alerts_enabled=True,
                                   record_sent_emails=True)
        self.current_config = None
        self.vip.config.set_default("config", self.default_config)

        self.vip.config.subscribe(self.configure_main,
                                  actions=["NEW", "UPDATE"], pattern="*")
	
        # Keep track of keys that have been added to send with.
        self.tosend = {}
        # Keep track of how often we send an email out based on key so we don't overload admins.
        self.sent_alert_emails = {}

    def _test_smtp_address(self, smtp_address,smtp_port,smtp_username,smtp_password):
        try:
            server = smtplib.SMTP(self.current_config.get('smtp_address', None),self.current_config.get('smtp_port', None))
            #stmplib docs recommend calling ehlo() before & after starttls()
            server.ehlo()
            if self.current_config.get('smtp_username') is not None:
                server.starttls()
                server.ehlo()
                server.login(self.current_config.get('smtp_username', None), self.current_config.get('smtp_password', None))
            server.close()
        except Exception as e:
            _log.error(e.args)


    def configure_main(self, config_name, action, contents):
        """
        The main configuration callback.

        :param config_name:
        :param action:
        :param contents:
        """

        self.vip.pubsub.subscribe('pubsub', topics.PLATFORM_SEND_EMAIL, self.on_email_message)

        self.vip.pubsub.subscribe('pubsub', topics.ALERTS_BASE,self.on_alert_message)
        self.vip.pubsub.subscribe('pubsub',prefix=topics.ALERTS.format(agent_class='',agent_identity=''),callback=self.on_alert_message)
        self.current_config = self.default_config.copy()
        self.current_config.update(contents)

        self.current_config['allow_frequency_seconds'] = self.current_config.get(
            'allow_frequency_minutes', 60) * 60

        smtp_address = self.current_config.get('smtp_address', None)
        smtp_port = self.current_config.get('smtp_port', None)
        smtp_username = self.current_config.get('smtp_username', None)
        smtp_password = self.current_config.get('smtp_password', None)
        if action == "UPDATE":
            try:
                with gevent.with_timeout(3, self._test_smtp_address, smtp_address,smtp_port,smtp_username,smtp_password):
                    pass
            except Exception as e:
                self.vip.health.set_status(STATUS_BAD, "Invalid SMTP Address")

    def on_email_message(self, peer, sender, bus, topic, headers, message):
        """
        Callback used for sending email messages through the pubsub bus.

        Either the from_address and to_addresses can be ommitted if they
        are specified in the configuration store/file.  If they are to be used
        the following block shows the format for usage.

        .. code-block:: json

            {
                "from-address": 'foo@bar.com',
                "to-addresses": ['alpha.beta@fo.com', 'bob-and-joe@bim.com']
            }

        ** In the above code to-addresses can be a singe email address as well**

        The message must be a dictionary containing a subject and a message.  In addition,
        an optional to-addresses entry can be added for sending to a specific group of
        users.

        .. code-block:: json

            {
                "subject": "I am a happy camper",
                "message": "This is a big long string message that I am sending"
                -- OPTIONAL --
                "to-addresses": ['yabba@daba.com']
            }

        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:
        """
        from_address = self.from_address
        to_addresses = self.to_address
        to_addresses = message.get("to-addresses", to_addresses)
        subject = message.get('subject', 'No Subject')
        msg = message.get('message', None)

        if msg is None:
            _log.error('Email messsage body was null, not sending email')
            return
        if to_addresses is None:
            _log.error('Email address not sent, to_addresses was None')
            return

        self.send_email(from_address, to_addresses, subject, msg)

    def _send_email(self, from_address, to_addresses, mime_message):
        """
        The method that actually sends the data to the smtp server to be
        sent out.

        This method will also publish to the record/sent_email topic so that
        the email action will be recorded.  The full message content will bw
        written to the message bus.  The following format is used

        .. code-block:: json

            {
                "from_address": from_address,
                "recipients": to_addresses,
                "subject": mime_message['Subject'],
                "message_content": mime_message.as_string()
            }

        :param from_address: The sender of the message
        :param to_addresses: A list of recipient email addresses.
        :param mime_message: A `email.mime.text.MimeText` message to be sent.
        """

        send_successful = False
        sent_email_record = None
        try:
            _log.info("Sending email {}".format(mime_message['Subject']))
            sent_email_record = {"from_address": from_address,
                                 "recipients": to_addresses,
                                 "subject": mime_message['Subject'],
                                 "message_content": mime_message.as_string()}
            cfg = self.current_config
            smtp_address = cfg['smtp_address']
            smtp_port = cfg['smtp_port']
            smtp_username = cfg['smtp_username']
            smtp_password = cfg['smtp_password']
            smtp_tls = cfg['smtp_tls']
            server = smtplib.SMTP(smtp_address, smtp_port)
            server.ehlo()

            if smtp_username is not None:
                server.starttls()
                server.ehlo()
                server.login(smtp_username, smtp_password)
            server.sendmail(from_address, to_addresses, mime_message.as_string())
            server.close()
            self.vip.health.set_status(STATUS_GOOD,
                                       "Successfully sent email.")
            send_successful = True
        except Exception as e:
            _log.error(
                'Unable to send email message: %s' % mime_message.as_string())
            _log.error(e.args)
            self.vip.health.set_status(STATUS_BAD,
                                       "Unable to send email to recipients")
        finally:
            if sent_email_record is not None:
                sent_email_record['successful'] = send_successful
                self.vip.pubsub.publish("pubsub", "record/sent_email",
                                        message=sent_email_record)

    def send_email(self, from_address, to_addresses, subject, message):
        """
        RPC Method allowing a platform to send an email address.

        One can also send an email through the pubsub mechanism.

        :param from_address:
        :param to_addresses:
        :param subject:
        :param message:
        """
        _log.info('Sending email {}'.format(subject))
        _log.debug('Mail from: {}, to: {}'.format(from_address, to_addresses))
        recipients = to_addresses
        if isinstance(recipients, str):
            recipients = [recipients]

        # Use unicode to protect against encod error
        # http://stackoverflow.com/questions/25891541/attributeerror-encode
        msg = MIMEText(str(message))
        msg['To'] = ', '.join(recipients)
        msg['FROM'] = from_address
        msg['Subject'] = subject

        gevent.spawn(self._send_email, from_address, recipients, msg)
        gevent.sleep(0.1)

    def on_alert_message(self, peer, sender, bus, topic, headers, message):
        """
        Callback for alert messages that come into the platform.

        :param peer:
        :param sender:
        :param bus:
        :param topic:
        :param headers:
        :param message:
        """
        if not self.current_config.get('send_alerts_enabled'):
            _log.warn('Alert message found but not sent enable alerts '
                      'enable by setting send_alerts_enabled to True')
            return
        mailkey = headers.get(ALERT_KEY, None)

        if not mailkey:
            _log.error("alert_key not found in header "
                       + "for message topic: {} message: {}"
                       .format(topic, message))
            return

        last_sent_key = tuple([mailkey, topic])
        if last_sent_key in self.tosend:
            return

        self.tosend[last_sent_key] = 1

        last_sent_time = self.sent_alert_emails.get(last_sent_key)

        should_send = False
        # python sets this to 0 if it hasn't ever been sent.
        if not last_sent_time:
            should_send = True
        else:
            current_time = get_utc_seconds_from_epoch()
            allow_frequency_seconds = self.current_config['allow_frequency_seconds']
            if last_sent_time + allow_frequency_seconds < current_time:
                should_send=True

        if not should_send:
            _log.debug('Waiting for time to pass for email.')
            if last_sent_key in self.tosend:
                del self.tosend[last_sent_key]
            return

        # we assume the email will go through.
        self.sent_alert_emails[last_sent_key] = get_utc_seconds_from_epoch()

        from_address = self.current_config['alert_from_address']
        recipients = self.current_config['alert_to_addresses']
        if isinstance(recipients, str):
            recipients = [recipients]

        # After here we are going to attempt to send the email out
        subject = "Alert for {} {}".format(topic, mailkey)

        # Use unicode to protect against encod error
        # http://stackoverflow.com/questions/25891541/attributeerror-encode
        msg = MIMEText(str(message))
        msg['To'] = ', '.join(recipients)
        msg['FROM'] = from_address
        msg['Subject'] = subject
        self.send_email(from_address, recipients, subject, msg)
        if last_sent_key in self.tosend:
            del self.tosend[last_sent_key]


def main(argv=sys.argv):
    """Main method called by the aip."""
    try:
        utils.vip_main(EmailerAgent, identity="platform.emailer",
                       version = __version__)
    except Exception as e:
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass



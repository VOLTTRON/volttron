# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:

# Copyright (c) 2015, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation
# are those of the authors and should not be interpreted as representing
# official policies, either expressed or implied, of the FreeBSD
# Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization that
# has cooperated in the development of these materials, makes any
# warranty, express or implied, or assumes any legal liability or
# responsibility for the accuracy, completeness, or usefulness or any
# information, apparatus, product, software, or process disclosed, or
# represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does not
# necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}
from __future__ import absolute_import, print_function

import datetime
# Import the email modules we'll need
from email.mime.text import MIMEText
import logging
import os
import socket
# Import smtplib for the actual sending function
import smtplib
import sys
import time
from urlparse import urlparse

import gevent
from zmq.utils import jsonapi

from volttron.platform.agent import utils
from volttron.platform.messaging import topics
from volttron.platform.messaging.health import ALERT_KEY
from volttron.platform.vip.agent import Agent, Core
from volttron.platform.vip.agent.subsystems import PubSub

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '1.0'


class EmailerAgent(Agent):
    """ The `EmailerAgent` is responsible for sending alert emails.

    The function of the `EmailerAgent` is to act as the sender of emails for
    a volttron instance.  This class works in conjunction with a volttron
    central instance to timely send emails to stakeholders.  This class's
    other responsability is to throttle the sending of emails so that the
    stakeholder is not bombarded with duplicate alerts.


    """

    def __init__(self, config_path, **kwargs):
        kwargs.pop("identity", None)
        super(EmailerAgent, self).__init__(identity="platform.emailer",
                                           **kwargs)

        config = utils.load_config(config_path)
        self._smtp = config.get("smtp-address", None)
        self._from = config.get("from-address", None)
        self._to = config.get("to-addresses", None)
        self._allow_frequency = config.get("allow-frequency-minutes", 60)
        self._allow_frequency_seconds = self._allow_frequency * 60
        if not self._from and self._to:
            raise ValueError('Invalid from/to addresses specified.')

        if self._smtp is None:
            raise ValueError('Invalid smtp-address')
        # will throw an error if can't connect
        try:
            s = smtplib.SMTP(self._smtp)
            s.quit()
        except socket.gaierror:
            raise ValueError('Invalid smtp-address')
	_log.debug('Allow frequency in seconds is: {}'.format(self._allow_frequency_seconds))
        self._sent_emails = None
        self._read_store()

    def timestamp(self):
        return time.mktime(datetime.datetime.now().timetuple())

    def _read_store(self):
        if os.path.exists('email.store'):
            with open('email.store', 'r') as f:
                self._sent_emails = jsonapi.loads(f.read())
        else:
            self._sent_emails = {}

    def _write_store(self):
        with open('email.store', 'w') as f:
            f.write(jsonapi.dumps(self._sent_emails))

    @PubSub.subscribe('pubsub',
                      prefix=topics.ALERTS.format(agent_class='',
                      agent_uuid=''))
    def onmessage(self, peer, sender, bus, topic, headers, message):
        _log.info('Alert message for topic: {}'.format(topic))
        _log.debug("Sending mail for message: {}".format(message))
        mailkey = headers.get(ALERT_KEY, None)
        if not mailkey:
            _log.error("alert_key not found in header "
                       + "for message topic: {} message: {}"
                       .format(topic, message))
            return

        # peal off the sent mail from the specific agent.
        if not topic in self._sent_emails.keys():
	    _log.debug('Topic not found: {}'.format(topic))
            self._sent_emails[topic] = {}

	sentmail = self._sent_emails[topic]
	
        if not mailkey in sentmail.keys():
            _log.debug('Mailkey not found: {}'.format(mailkey))
	    sentmail[mailkey] = 0
        
        sentlast = sentmail[mailkey]
        _log.debug('Sentlast is now: {}'.format(sentlast))
        should_send = False
        current_time = self.timestamp()
       
        if not sentlast:
            # first time sending
            should_send = True
        elif current_time > sentlast + self._allow_frequency_seconds:
            _log.debug("sentlast: {}".format(sentlast))
            _log.debug("sentlast+seconds: {}".format(sentlast+self._allow_frequency_seconds))
            should_send = True
	
	if should_send:
            subject = "Alert for {} {}".format(topic, mailkey)
            self._send_alert_mail(subject, message)
            debugmsg = "current_time: {} next send time: {} _sent_emails[{}][{}]"
            _log.debug(debugmsg.format(current_time, current_time+self._allow_frequency_seconds,
                topic, mailkey)) 
            self._sent_emails[topic][mailkey] = current_time
            self._write_store()
            _log.debug('SENT EMAILS: {}'.format(self._sent_emails))
        else:
            _log.debug('SKIPPING EMAIL for topic: {}'.format(topic))


    def _send_alert_mail(self, subject, message):
        _log.debug('Sending mail {}\nmessage:\n{}'.format(subject, message))
        _log.debug('Mail from: {}, to: {}'.format(self._from, self._to))
        recipients = self._to
        if isinstance(recipients, basestring):
            recipients = [recipients]

	msg = MIMEText(message)
        msg['To'] = ', '.join(recipients)
        msg['FROM'] = self._from
        msg['Subject'] = subject

	_log.debug('MESSAGE: {}'.format(msg.as_string()))
        s = smtplib.SMTP(self._smtp)
        s.sendmail(self._from, recipients, msg.as_string())
        s.quit() 


# def main(argv=sys.argv):
#     '''Main method called by the aip.'''
#     try:
#         utils.vip_main(EmailerAgent)
#     except Exception as e:
#         print(e)
#         _log.exception('unhandled exception')
#
#
# if __name__ == '__main__':
#     # Entry point for script
#     try:
#         sys.exit(main())
#     except KeyboardInterrupt:
#         pass


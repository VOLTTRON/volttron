# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2017, Battelle Memorial Institute.
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

from datetime import timedelta
import isodate
import json
import logging
import random
import time

from volttron.platform.agent import utils

from oadr_common import *

utils.setup_logging()
_log = logging.getLogger(__name__)


class OadrExtractor(object):
    """Extract oadr model objects received from the VTN as XML."""

    def __init__(self, request=None, **kwargs):
        self.request = request

    def extract_request_id(self):
        request_id = self.request.requestID
        if request_id is None:
            raise OpenADRInterfaceException('Missing requestID', OADR_BAD_DATA)
        return request_id

    @staticmethod
    def extract_start_and_end_time(interval):
        """Extract a start_time and an end_time from a received interval."""
        try:
            start_time = interval.properties.dtstart.date_time
            assert start_time is not None
            assert start_time.tzinfo is not None
        except Exception, err:
            error_msg = 'Missing/Invalid interval properties.dtstart.date_time: {} {}'.format(start_time, err)
            raise OpenADRInterfaceException(error_msg, OADR_BAD_DATA)

        try:
            duration = interval.properties.duration.duration
            parsed_duration = isodate.parse_duration(duration)
        except Exception, err:
            error_msg = 'Missing/Invalid interval properties.duration.duration: {} {}'.format(duration, err)
            raise OpenADRInterfaceException(error_msg, OADR_BAD_DATA)

        # An interval with 0 duration has no defined endTime and remains active until canceled.
        end_time = None if parsed_duration.total_seconds() == 0.0 else start_time + parsed_duration
        return start_time, end_time


class OadrResponseExtractor(OadrExtractor):

    def __init__(self, ei_response=None, **kwargs):
        super(OadrResponseExtractor, self).__init__(**kwargs)
        self.ei_response = ei_response

    def extract(self):
        """An eiResponse can appear in multiple kinds of VTN requests. Extract its code and description."""
        return self.ei_response.responseCode, self.ei_response.responseDescription


class OadrEventExtractor(OadrExtractor):
    """Extract an event's properties from oadr model objects received from the VTN as XML."""

    def __init__(self, event=None, ei_event=None, **kwargs):
        super(OadrEventExtractor, self).__init__(**kwargs)
        self.event = event
        self.ei_event = ei_event

    def extract_event_descriptor(self):
        """Extract eventDescriptor data from the received eiEvent, populating the temporary EiEvent."""
        event_descriptor = self.ei_event.eventDescriptor

        # OADR rule 13: Status value must be a valid type, appropriate for the event's period.
        self.event.status = event_descriptor.eventStatus
        if self.event.status not in self.event.STATUS_VALUES:
            raise OpenADRInterfaceException('Missing or invalid eventDescriptor.eventStatus', OADR_BAD_DATA)

        self.event.modification_number = event_descriptor.modificationNumber
        if self.event.modification_number is None:
            raise OpenADRInterfaceException('Missing eventDescriptor.modificationNumber', OADR_BAD_DATA)

        not_used = event_descriptor.modificationReason

        if event_descriptor.priority:
            self.event.priority = event_descriptor.priority

        market_context_holder = event_descriptor.eiMarketContext
        if market_context_holder:
            # OADR rule 48: Allow any valid URI as a marketContext (e.g., *).
            not_used = market_context_holder.marketContext
        not_used = event_descriptor.createdDateTime
        test_flag = event_descriptor.testEvent
        if test_flag:
            self.event.test_event = test_flag
        not_used = event_descriptor.vtnComment

    def extract_active_period(self):
        """Validate eiActivePeriod data in the received eiEvent."""
        active_period = self.ei_event.eiActivePeriod
        if active_period is None:
            raise OpenADRInterfaceException('Missing eiEvent.eiActivePeriod', OADR_BAD_DATA)

        properties = active_period.properties
        if properties is None:
            raise OpenADRInterfaceException('Missing eiEvent.eiActivePeriod.properties', OADR_BAD_DATA)

        try:
            self.event.dtstart = properties.dtstart.date_time
            assert self.event.dtstart is not None
            assert self.event.dtstart.tzinfo is not None
        except Exception, err:
            error_msg = 'Missing/Invalid properties.dtstart.date_time: {} {}'.format(properties.dtstart.date_time, err)
            raise OpenADRInterfaceException(error_msg, OADR_BAD_DATA)

        try:
            self.event.duration = properties.duration.duration
            event_length = isodate.parse_duration(properties.duration.duration)
        except Exception, err:
            error_msg = 'Missing/Invalid properties.duration.duration: {} {}'.format(properties.duration.duration, err)
            raise OpenADRInterfaceException(error_msg, OADR_BAD_DATA)

        active_period_props = active_period.properties

        if active_period_props.tolerance and active_period_props.tolerance.tolerate:
            self.event.start_after = active_period_props.tolerance.tolerate.startafter
        else:
            self.event.start_after = None

        if self.event.start_after:
            try:
                max_offset = isodate.parse_duration(self.event.start_after)
                # OADR rule 30: Randomize start_time and end_time if start_after is provided.
                self.event.start_time = self.event.dtstart + timedelta(seconds=(max_offset.seconds * random.random()))
            except Exception, err:
                error_msg = 'Invalid activePeriod tolerance.tolerate.startafter: {}'.format(err)
                raise OpenADRInterfaceException(error_msg, OADR_BAD_DATA)
        else:
            self.event.start_time = self.event.dtstart

        # An interval with 0 duration has no defined endTime and remains active until canceled.
        self.event.end_time = self.event.start_time + event_length if event_length.total_seconds() > 0.0 else None

        notification = active_period_props.x_eiNotification
        if notification is None:
            # OADR rule 105: eiNotification is required as an element of activePeriod.
            raise OpenADRInterfaceException('Missing eiActivePeriod.properties.eiNotification', OADR_BAD_DATA)

        not_used = notification.duration

        ramp_up = active_period_props.x_eiRampUp
        if ramp_up is not None:
            not_used = ramp_up.duration
        recovery = active_period_props.x_eiRecovery
        if recovery is not None:
            not_used = recovery.duration

    def extract_signals(self):
        """Extract eiEventSignals from the received eiEvent, populating the temporary EiEvent."""
        if not self.ei_event.eiEventSignals:
            raise OpenADRInterfaceException('At least one event signal is required.', OADR_BAD_SIGNAL)
        if not self.ei_event.eiEventSignals.eiEventSignal:
            raise OpenADRInterfaceException('At least one event signal is required.', OADR_BAD_SIGNAL)
        signals_dict = {s.signalID: self.extract_signal(s) for s in self.ei_event.eiEventSignals.eiEventSignal}
        self.event.signals = json.dumps(signals_dict)
        # Sum of all signal interval durations must equal the event duration.
        signals_duration = timedelta(seconds=0)
        for signal in self.ei_event.eiEventSignals.eiEventSignal:
            for interval in signal.intervals.interval:
                signals_duration += isodate.parse_duration(interval.duration.duration)
        event_duration = isodate.parse_duration(self.event.duration)
        if signals_duration != event_duration:
            err_msg = 'Total signal interval durations {} != event duration {}'.format(signals_duration, event_duration)
            raise OpenADRException(err_msg, OADR_BAD_SIGNAL)

    @staticmethod
    def extract_signal(signal):
        """Extract a signal from the received eiEvent."""
        if signal.signalName.lower() != 'simple':
            raise OpenADRInterfaceException('Received a non-simple event signal; not supported by this VEN.', OADR_BAD_SIGNAL)
        if signal.signalType.lower() != 'level':
            # OADR rule 116: If signalName = simple, signalType = level.
            # Disabling this validation since the EPRI VTN server sometimes sends type "delta" for simple signals.
            # error_msg = 'Simple signalType must be level; = {}'.format(signal.signalType)
            # raise OpenADRInterfaceException(error_msg, OADR_BAD_SIGNAL)
            pass
        return {
            'signalID': signal.signalID,
            'currentLevel': int(signal.currentValue.payloadFloat.value) if signal.currentValue else None,
            'intervals': {
                interval.uid if interval.uid and interval.uid.strip() else str(i): {
                    'uid': interval.uid if interval.uid and interval.uid.strip() else str(i),
                    'duration': interval.duration.duration,
                    'payloads': {'level': int(payload.payloadBase.value) for payload in interval.streamPayloadBase}
                } for i, interval in enumerate(signal.intervals.interval)}
        }


class OadrReportExtractor(OadrExtractor):
    """Extract a report's properties from oadr model objects received from the VTN as XML."""

    def __init__(self, report=None, report_parameters=None, **kwargs):
        super(OadrReportExtractor, self).__init__(**kwargs)
        self.report = report
        self.report_parameters = report_parameters

    def extract_report_request_id(self):
        """Extract and return the report's reportRequestID."""
        report_request_id = self.request.reportRequestID
        if report_request_id is None:
            raise OpenADRInterfaceException('Missing oadrReportRequest.reportRequestID', OADR_BAD_DATA)
        return report_request_id

    def extract_specifier_id(self):
        """Extract and return the report's reportSpecifierID."""
        report_specifier = self.request.reportSpecifier
        if report_specifier is None:
            raise OpenADRInterfaceException('Missing oadrReportRequest.reportSpecifier', OADR_BAD_DATA)
        report_specifier_id = report_specifier.reportSpecifierID
        if report_specifier_id is None:
            error_msg = 'Missing oadrReportRequest.reportSpecifier.reportSpecifierID'
            raise OpenADRInterfaceException(error_msg, OADR_BAD_DATA)
        return report_specifier_id

    def extract_report(self):
        """Validate various received report fields and add them to the report instance."""
        report_specifier = self.request.reportSpecifier
        report_interval = report_specifier.reportInterval
        if report_interval is None:
            raise OpenADRInterfaceException('Missing reportInterval', OADR_BAD_DATA)

        try:
            start_time = report_interval.properties.dtstart.date_time
            assert start_time is not None
            assert start_time.tzinfo is not None
        except Exception, err:
            error_msg = 'Missing/Invalid interval properties.dtstart.date_time: {} {}'.format(start_time, err)
            raise OpenADRInterfaceException(error_msg, OADR_BAD_DATA)

        try:
            duration = report_interval.properties.duration.duration
            end_time = start_time + isodate.parse_duration(duration)
        except Exception, err:
            # To accommodate the Kisensum VTN server, a report interval with a missing/null duration
            # has a special meaning to the VEN: the report request continues indefinitely,
            # with no scheduled completion time.
            _log.debug('Missing/null report interval duration: the report will remain active indefinitely.')
            duration = None
            end_time = None

        self.report.start_time = start_time
        self.report.end_time = end_time
        self.report.duration = duration

        self.report.name = self.report_parameters.get('report_name', None)
        self.report.telemetry_parameters = json.dumps(self.report_parameters.get('telemetry_parameters', None))

        default = self.report_parameters.get('report_interval_secs_default')
        iso_duration = report_specifier.reportBackDuration
        if iso_duration is not None:
            try:
                self.report.interval_secs = int(isodate.parse_duration(iso_duration.duration).total_seconds())
            except Exception, err:
                error_msg = 'reportBackDuration {} has unparsable duration: {}'.format(dur, err)
                raise OpenADRInterfaceException(error_msg, OADR_BAD_DATA)
        elif default is not None:
            try:
                self.report.interval_secs = int(default)
            except ValueError:
                error_msg = 'Default report interval {} is not an integer number of seconds'.format(default)
                raise OpenADRInterfaceException(error_msg, OADR_BAD_DATA)
        else:
            self.report.interval_secs = None

        if report_specifier.granularity:
            try:
                granularity = isodate.parse_duration(report_specifier.granularity.duration)
                self.report.granularity_secs = int(granularity.total_seconds())
            except Exception:
                error_msg = 'Report granularity is missing or is not an ISO8601 duration'
                raise OpenADRInterfaceException(error_msg, OADR_BAD_DATA)


class OadrRegistrationExtractor(OadrExtractor):

    def __init__(self, **kwargs):
        super(OadrRegistrationExtractor, self).__init__(**kwargs)


class OadrCreatedPartyRegistrationExtractor(OadrRegistrationExtractor):

    def __init__(self, registration=None, **kwargs):
        super(OadrCreatedPartyRegistrationExtractor, self).__init__(**kwargs)
        self.registration = registration

    def extract_ven_id(self):
        return self.registration.venID

    def extract_poll_freq(self):
        return self.registration.oadrRequestedOadrPollFreq

    def extract_vtn_id(self):
        return self.registration.vtnID

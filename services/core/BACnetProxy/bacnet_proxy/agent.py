# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
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

import logging
import sys
import datetime

from volttron.platform.vip.agent import Agent, RPC
from volttron.platform.async_ import AsyncCall
from volttron.platform.agent import utils
from volttron.platform.messaging import topics, headers

utils.setup_logging()
_log = logging.getLogger(__name__)

bacnet_logger = logging.getLogger("bacpypes")
bacnet_logger.setLevel(logging.WARNING)
__version__ = '0.5'

from collections import defaultdict

from queue import Queue, Empty

from bacpypes.task import RecurringTask

import bacpypes.core

import threading

# Tweeks to BACpypes to make it play nice with Gevent.
bacpypes.core.enable_sleeping()

from bacpypes.pdu import Address, GlobalBroadcast
from bacpypes.app import BIPSimpleApplication
from bacpypes.service.device import LocalDeviceObject
from bacpypes.object import get_datatype

from bacpypes.apdu import (ReadPropertyRequest,
                           WritePropertyRequest,
                           Error,
                           AbortPDU,
                           RejectPDU,
                           ReadPropertyACK,
                           SimpleAckPDU,
                           ReadPropertyMultipleRequest,
                           ReadPropertyMultipleACK,
                           PropertyReference,
                           ReadAccessSpecification,
                           encode_max_apdu_length_accepted,
                           WhoIsRequest,
                           IAmRequest,
                           ConfirmedRequestSequence,
                           SubscribeCOVRequest,
                           ConfirmedCOVNotificationRequest)
from bacpypes.primitivedata import (Null, Atomic, Enumerated, Integer,
                                    Unsigned, Real)
from bacpypes.constructeddata import Array, Any, Choice
from bacpypes.basetypes import ServicesSupported
from bacpypes.task import TaskManager
from gevent.event import AsyncResult

from volttron.platform.agent.known_identities import PLATFORM_DRIVER

# Make sure the TaskManager singleton exists...
task_manager = TaskManager()


class SubscriptionContext(object):
    """
    Object for maintaining BACnet change of value subscriptions with points on a device
    """

    def __init__(self, device_path, address, point_name, object_type, instance_number, sub_process_id, lifetime=None):

        self.device_path = device_path
        self.device_address = address

        # Arbitrary value which ties COVRequests to a subscription object
        self.subscriberProcessIdentifier = sub_process_id

        self.point_name = point_name
        self.monitoredObjectIdentifier = (object_type, instance_number)
        self.lifetime = lifetime


class BACnetApplication(BIPSimpleApplication, RecurringTask):
    def __init__(self, i_am_callback, send_cov_subscription_callback, forward_cov_callback, request_check_interval,
                 *args):
        BIPSimpleApplication.__init__(self, *args)
        RecurringTask.__init__(self, request_check_interval)

        self.i_am_callback = i_am_callback
        self.send_cov_subscription_callback = send_cov_subscription_callback
        self.forward_cov_callback = forward_cov_callback

        self.request_queue = Queue()

        # assigning invoke identifiers
        self.nextInvokeID = 1

        # keep track of requests to line up responses
        self.iocb = {}

        # Tracking mechanism for matching COVNotifications to a COV
        # subscriptionContext object
        self.sub_cov_contexts = {}
        self.cov_sub_process_ID = 1

        self.install_task()

    def process_task(self):
        while True:
            try:
                iocb = self.request_queue.get(False)
            except Empty:
                break

            self.handle_request(iocb)

    def submit_request(self, iocb):
        self.request_queue.put(iocb)

    def get_next_invoke_id(self, addr):
        """Called to get an unused invoke ID."""

        initial_id = self.nextInvokeID
        while 1:
            invoke_id = self.nextInvokeID
            self.nextInvokeID = (self.nextInvokeID + 1) % 256

            # see if we've checked for them all
            if initial_id == self.nextInvokeID:
                raise RuntimeError("no available invoke ID")

            # see if this one is used
            if (addr, invoke_id) not in self.iocb:
                break

        return invoke_id

    def handle_request(self, iocb):
        apdu = iocb.ioRequest

        if isinstance(apdu, ConfirmedRequestSequence):
            # assign an invoke identifier
            apdu.apduInvokeID = self.get_next_invoke_id(apdu.pduDestination)

            # build a key to reference the IOCB when the response comes back
            invoke_key = (apdu.pduDestination, apdu.apduInvokeID)

            # keep track of the request
            self.iocb[invoke_key] = iocb

        try:
            self.request(apdu)
        except Exception as e:
            iocb.set_exception(e)

    def _get_iocb_key_for_apdu(self, apdu):
        return apdu.pduSource, apdu.apduInvokeID

    def _get_iocb_for_apdu(self, apdu, invoke_key):
        # find the request
        working_iocb = self.iocb.get(invoke_key, None)
        if working_iocb is None:
            _log.error("no matching request for confirmation")
            return None
        del self.iocb[invoke_key]

        if isinstance(apdu, AbortPDU):
            working_iocb.set_exception(RuntimeError("Device communication aborted: " + str(apdu)))
            return None

        elif isinstance(apdu, Error):
            working_iocb.set_exception(RuntimeError("Error during device communication: " + str(apdu)))
            return None
        elif isinstance(apdu, RejectPDU):
            working_iocb.set_exception(
                RuntimeError("Device at {source} rejected the request: {reason}".format(
                    source=apdu.pduSource, reason=apdu.apduAbortRejectReason)))
            return None
        else:
            return working_iocb

    def _get_value_from_read_property_request(self, apdu, working_iocb):
        # find the datatype

        #_log.debug("WIGGEDYWACKYO")

        datatype = get_datatype(apdu.objectIdentifier[0], apdu.propertyIdentifier)
        if not datatype:
            working_iocb.set_exception(TypeError("unknown datatype"))
            return

        # special case for array parts, others are managed by cast_out
        if issubclass(datatype, Array) and apdu.propertyArrayIndex is not None:
            if apdu.propertyArrayIndex == 0:
                value = apdu.propertyValue.cast_out(Unsigned)
            else:
                value = apdu.propertyValue.cast_out(datatype.subtype)
        else:
            value = apdu.propertyValue.cast_out(datatype)
            if issubclass(datatype, Enumerated):
                value = datatype(value).get_long()
        return value

    def _get_value_from_property_value(self, property_value, datatype, working_iocb):
        value = property_value.cast_out(datatype)
        if issubclass(datatype, Enumerated):
            value = datatype(value).get_long()

        try:
            if issubclass(datatype, Array) and issubclass(datatype.subtype, Choice):
                new_value = []
                for item in value.value[1:]:
                    result = list(item.dict_contents().values())
                    if result[0] != ():
                        new_value.append(result[0])
                    else:
                        new_value.append(None)
                value = new_value
        except Exception as e:
            _log.exception(e)
            working_iocb.set_exception(e)
            return
        return value

    def confirmation(self, apdu):
        # return iocb if exists, otherwise sets error and returns
        invoke_key = self._get_iocb_key_for_apdu(apdu)
        working_iocb = self._get_iocb_for_apdu(apdu, invoke_key)
        if not working_iocb:
            return

        if isinstance(working_iocb.ioRequest, ReadPropertyRequest) and isinstance(apdu, ReadPropertyACK):
            # handle receiving covIncrement read results by calling
            # the send_cov_subscription callback if a subscription exists and
            # the covIncrement is valid
            value = self._get_value_from_read_property_request(apdu, working_iocb)
            if apdu.propertyIdentifier == 'covIncrement':
                _log.debug("received read covIncrement property response from {}".format(apdu.pduSource))
                subscription = None
                subscription_id = -1
                for key, sub in self.sub_cov_contexts.items():
                    if sub.device_address == apdu.pduSource and \
                       sub.monitoredObjectIdentifier[0] == apdu.objectIdentifier[0] and \
                       sub.monitoredObjectIdentifier[1] == apdu.objectIdentifier[1]:
                        subscription = sub
                        subscription_id = key
                if subscription:
                    if value:
                        _log.info("covIncrement is {} for point {} on device".format(
                            value, subscription.point_name, subscription.device_path))
                        self.send_cov_subscription_callback(apdu.pduSource,
                                                            subscription.subscriberProcessIdentifier,
                                                            subscription.monitoredObjectIdentifier,
                                                            subscription.lifetime,
                                                            subscription.point_name)
                    else:
                        _log.warning("point {} on device {} does not have a valid covIncrement property")
                        self.bacnet_application.sub_cov_contexts.pop(subscription_id)
                else:
                    _log.error('Received read covIncrement response, but no subscription context exists for {} on {}'.
                               format(subscription.device_path, subscription.point_name))
            else:
                working_iocb.set(value)
            return

        elif isinstance(working_iocb.ioRequest, WritePropertyRequest) and isinstance(apdu, SimpleAckPDU):
            working_iocb.set(apdu)
            return

        # Simple record-keeping for subscription request responses
        elif isinstance(working_iocb.ioRequest, SubscribeCOVRequest) and isinstance(apdu, SimpleAckPDU):
            _log.debug("COV subscription established for {} on {}".format(
                working_iocb.ioRequest.monitoredObjectIdentifer, working_iocb.ioRequest.pduSource))
            working_iocb.set(apdu)
            return
        elif isinstance(working_iocb.ioRequest, SubscribeCOVRequest) and not isinstance(apdu, SimpleAckPDU):
            _log.error("The SubscribeCOVRequest for {} failed to establish a subscription.".format(
                SubscribeCOVRequest.monitoredObjectIdentifier))
            return

        elif isinstance(working_iocb.ioRequest, ReadPropertyMultipleRequest) and \
            isinstance(apdu, ReadPropertyMultipleACK):

            result_dict = {}
            for result in apdu.listOfReadAccessResults:
                # here is the object identifier
                object_identifier = result.objectIdentifier

                # now come the property values per object
                for element in result.listOfResults:
                    # get the property and array index
                    property_identifier = element.propertyIdentifier
                    property_array_index = element.propertyArrayIndex

                    # here is the read result
                    read_result = element.readResult

                    # check for an error
                    if read_result.propertyAccessError is not None:
                        error_obj = read_result.propertyAccessError

                        msg = 'ERROR DURING SCRAPE of {2} (Class: {0} Code: {1})'
                        _log.error(msg.format(error_obj.errorClass, error_obj.errorCode, object_identifier))

                    else:
                        # here is the value
                        property_value = read_result.propertyValue

                        # find the datatype
                        datatype = get_datatype(object_identifier[0], property_identifier)
                        if not datatype:
                            working_iocb.set_exception(TypeError("unknown datatype"))
                            return

                        # special case for array parts, others are managed
                        # by cast_out
                        if issubclass(datatype, Array) and property_array_index is not None:
                            if property_array_index == 0:
                                value = property_value.cast_out(Unsigned)
                            else:
                                value = property_value.cast_out(datatype.subtype)
                        else:
                            value = self._get_value_from_property_value(property_value, datatype, working_iocb)

                        result_dict[object_identifier[0], object_identifier[1], property_identifier,
                                    property_array_index] = value

            working_iocb.set(result_dict)

        else:
            _log.error("For invoke key {key} Unsupported Request Response pair Request: {request} Response: {response}".
                       format(key=invoke_key, request=working_iocb.ioRequest, response=apdu))
            working_iocb.set_exception(TypeError('Unsupported Request Type'))

    def indication(self, apdu):
        if isinstance(apdu, IAmRequest):
            device_type, device_instance = apdu.iAmDeviceIdentifier
            if device_type != 'device':
                # Bail without an error.
                return

            _log.debug("Calling IAm callback.")

            self.i_am_callback(str(apdu.pduSource),
                               device_instance,
                               apdu.maxAPDULengthAccepted,
                               str(apdu.segmentationSupported),
                               apdu.vendorID)

        elif isinstance(apdu, ConfirmedCOVNotificationRequest):
            # Handling for ConfirmedCOVNotificationRequests. These requests are
            # sent by the device when a point with a COV subscription updates
            # past the covIncrement threshold(See COV_Detection class in
            # Bacpypes:
            # https://bacpypes.readthedocs.io/en/latest/modules/service/cov.html)
            _log.debug("ConfirmedCOVNotificationRequest received from {}".format(apdu.pduSource))
            point_name = None
            device_path = None

            result_dict = {}
            for element in apdu.listOfValues:
                property_id = element.propertyIdentifier
                if not property_id == "statusFlags":
                    values = []
                    for tag in element.value.tagList:
                        values.append(tag.app_to_object().value)
                    if len(values) == 1:
                        result_dict[property_id] = values[0]
                    else:
                        result_dict[property_id] = values

            if result_dict:
                context = self.sub_cov_contexts[apdu.subscriberProcessIdentifier]
                point_name = context.point_name
                device_path = context.device_path

            if point_name and device_path:
                self.forward_cov_callback(device_path, point_name, result_dict)
            else:
                _log.debug("Device {} does not have a subscription context.".format(apdu.monitoredObjectIdentifier))

        # forward it along
        BIPSimpleApplication.indication(self, apdu)


write_debug_str = "Writing: {target} {type} {instance} {property} (Priority: {priority}, Index: {index}): {value}"


def bacnet_proxy_agent(config_path, **kwargs):
    config = utils.load_config(config_path)
    device_address = config["device_address"]
    max_apdu_len = config.get("max_apdu_length", 1024)
    seg_supported = config.get("segmentation_supported", "segmentedBoth")
    obj_id = config.get("object_id", 599)
    obj_name = config.get("object_name", "Volttron BACnet driver")
    ven_id = config.get("vendor_id", 15)
    max_per_request = config.get("default_max_per_request", 1000000)
    request_check_interval = config.get("request_check_interval", 100)

    return BACnetProxyAgent(device_address, max_apdu_len, seg_supported, obj_id, obj_name, ven_id, max_per_request,
                            request_check_interval=request_check_interval, heartbeat_autostart=True, **kwargs)


class BACnetProxyAgent(Agent):
    """
    This agent creates a virtual bacnet device that is used by the bacnet driver interface to communicate with devices.
    """
    def __init__(self, device_address, max_apdu_len, seg_supported, obj_id, obj_name, ven_id, max_per_request,
                 request_check_interval=100, **kwargs):
        super(BACnetProxyAgent, self).__init__(**kwargs)

        async_call = AsyncCall()
        self.bacnet_application = None

        # IO callback
        class IOCB:
            def __init__(self, request):
                # requests and responses
                self.ioRequest = request
                self.ioResult = AsyncResult()

            def set(self, value):
                async_call.send(None, self.ioResult.set, value)

            def set_exception(self, exception):
                async_call.send(None, self.ioResult.set_exception, exception)

        self.iocb_class = IOCB
        self._max_per_request = max_per_request

        self.setup_device(async_call, device_address, max_apdu_len, seg_supported, obj_id, obj_name, ven_id,
                          request_check_interval)

    def setup_device(self, async_call, address,
                     max_apdu_len=1024,
                     seg_supported='segmentedBoth',
                     obj_id=599,
                     obj_name='sMap BACnet driver',
                     ven_id=15,
                     request_check_interval=100):

        _log.info('seg_supported '+str(seg_supported))
        _log.info('max_apdu_len '+str(max_apdu_len))
        _log.info('obj_id '+str(obj_id))
        _log.info('obj_name '+str(obj_name))
        _log.info('ven_id '+str(ven_id))

        # Check to see if they gave a valid apdu length.
        if encode_max_apdu_length_accepted(max_apdu_len) is None:
            raise ValueError("Invalid max_apdu_len: {} Valid options are 50, 128, 206, 480, 1024, and 1476".format(
                             max_apdu_len))

        this_device = LocalDeviceObject(
            objectName=obj_name,
            objectIdentifier=obj_id,
            maxApduLengthAccepted=max_apdu_len,
            segmentationSupported=seg_supported,
            vendorIdentifier=ven_id,
            )

        # build a bit string that knows about the bit names.
        pss = ServicesSupported()
        pss['whoIs'] = 1
        pss['iAm'] = 1

        # set the property value to be just the bits
        this_device.protocolServicesSupported = pss.value

        def i_am_callback(address, device_id, max_apdu_len, seg_supported, vendor_id):
            async_call.send(None, self.i_am, address, device_id, max_apdu_len, seg_supported, vendor_id)

        def send_cov_subscription_callback(device_address, subscriber_process_identifier, monitored_object_identifier,
                                           lifetime, point_name):
            """
            Asynchronous cov subscription callback for gevent
            """
            async_call.send(None, self.send_cov_subscription, device_address, subscriber_process_identifier,
                            monitored_object_identifier, lifetime, point_name)

        def forward_cov_callback(point_name, apdu, result_dict):
            """
            Asynchronous callback to forward cov values to the master driver
            for gevent
            """
            async_call.send(None, self.forward_cov, point_name, apdu, result_dict)

        self.bacnet_application = BACnetApplication(i_am_callback,
                                                    send_cov_subscription_callback,
                                                    forward_cov_callback,
                                                    request_check_interval,
                                                    this_device,
                                                    address)

        # Having a recurring task makes the spin value kind of irrelevant.
        kwargs = {"spin": 0.1,
                  "sigterm": None,
                  "sigusr1": None}

        server_thread = threading.Thread(target=bacpypes.core.run, kwargs=kwargs)

        # exit the BACnet App thread when the main thread terminates
        server_thread.daemon = True
        server_thread.start()

    def i_am(self, address, device_id, max_apdu_len, seg_supported, vendor_id):
        """
        Called by the BACnet application when a WhoIs is received. Publishes the IAm to the pubsub.
        """
        _log.debug("IAm received: Address: {} Device ID: {} Max APDU: {} Segmentation: {} Vendor: {}".format(
            address, device_id, max_apdu_len, seg_supported, vendor_id))

        header = {headers.TIMESTAMP: utils.format_timestamp(datetime.datetime.utcnow())}
        value = {"address": address,
                 "device_id": device_id,
                 "max_apdu_length": max_apdu_len,
                 "segmentation_supported": seg_supported,
                 "vendor_id": vendor_id}

        self.vip.pubsub.publish('pubsub', topics.BACNET_I_AM, header, message=value)

    def forward_cov(self, device_path, point_name, result_dict):
        """
        Called by the BACnet application when a ConfirmedCOVNotification Request
        is received. Publishes the COV to the pubsub through the device's
        driver agent
        :param device_path: path of the device for use in publish topic
        :param point_name: COV notification contains values for this point
        :param result_dict: dictionary of values from the point
        """
        self.vip.rpc.call(PLATFORM_DRIVER, 'forward_bacnet_cov_value', device_path, point_name, result_dict)

    @RPC.export
    def who_is(self, low_device_id=None, high_device_id=None, target_address=None):
        _log.debug("Sending WhoIs: low_id: {low} high: {high} address: {address}".format(
            low=low_device_id, high=high_device_id, address=target_address))
        request = WhoIsRequest()

        if low_device_id is not None:
            request.deviceInstanceRangeLowLimit = low_device_id
        if high_device_id is not None:
            request.deviceInstanceRangeHighLimit = high_device_id

        if target_address is not None:
            request.pduDestination = Address(target_address)
        else:
            request.pduDestination = GlobalBroadcast()

        iocb = self.iocb_class(request)
        self.bacnet_application.submit_request(iocb)

    @RPC.export
    def ping_device(self, target_address, device_id):
        """
        Ping a device with a whois to potentially setup routing.
        """
        _log.debug("Pinging " + target_address)
        self.who_is(device_id, device_id, target_address)

    def _cast_value(self, value, datatype):
            if datatype is Integer:
                value = int(value)
            elif datatype is Real:
                value = float(value)
            elif datatype is Unsigned:
                value = int(value)
            return datatype(value)

    @RPC.export
    def write_property(self, target_address, value, object_type, instance_number, property_name, priority=None,
                       index=None):
        """
        Write to a property.
        """

        _log.debug(write_debug_str.format(target=target_address,
                                          type=object_type,
                                          instance=instance_number,
                                          property=property_name,
                                          priority=priority,
                                          index=index,
                                          value=value))

        request = WritePropertyRequest(objectIdentifier=(object_type, instance_number),
                                       propertyIdentifier=property_name)

        datatype = get_datatype(object_type, property_name)
        bac_value = None
        if value is None or value == 'null':
            bac_value = Null()
        elif issubclass(datatype, Atomic):
            bac_value = self._cast_value(value, datatype)
        elif issubclass(datatype, Array) and (index is not None):
            if index == 0:
                bac_value = Integer(value)
            elif issubclass(datatype.subtype, Atomic):
                bac_value = datatype.subtype(value)
            elif not isinstance(value, datatype.subtype):
                raise TypeError("invalid result datatype, expecting {}".format(datatype.subtype.__name__,))
        elif not isinstance(value, datatype):
            raise TypeError("invalid result datatype, expecting %s".format(datatype.__name__,))

        request.propertyValue = Any()
        request.propertyValue.cast_in(bac_value)

        request.pduDestination = Address(target_address)

        # Optional index
        if index is not None:
            request.propertyArrayIndex = index

        # Optional priority
        if priority is not None:
            request.priority = priority

        iocb = self.iocb_class(request)
        self.bacnet_application.submit_request(iocb)
        result = iocb.ioResult.get(10)
        if isinstance(result, SimpleAckPDU):
            return value
        raise RuntimeError("Failed to set value: " + str(result))

    def read_using_single_request(self, target_address, point_map):
        results = {}

        for point, properties in point_map.items():
            if len(properties) == 3:
                object_type, instance_number, property_name = properties
                property_index = None
            elif len(properties) == 4:
                (object_type, instance_number, property_name,
                 property_index) = properties
            else:
                _log.error("skipping {} in request to {}: incorrect number of parameters".format(point, target_address))
                continue

            try:
                results[point] = self.read_property(
                    target_address, object_type, instance_number, property_name, property_index)
            except Exception as e:
                _log.error("Error reading point {} from {}: {}".format(point, target_address, e))

        return results

    @RPC.export
    def read_property(self, target_address, object_type, instance_number, property_name, property_index=None):
        request = ReadPropertyRequest(
            objectIdentifier=(object_type, instance_number),
            propertyIdentifier=property_name,
            propertyArrayIndex=property_index)
        request.pduDestination = Address(target_address)
        iocb = self.iocb_class(request)
        self.bacnet_application.submit_request(iocb)
        bacnet_results = iocb.ioResult.get(10)
        return bacnet_results

    def _get_access_spec(self, obj_data, properties):
        count = 0
        obj_type, obj_inst = obj_data
        prop_ref_list = []
        for prop, prop_index in properties:
            prop_ref = PropertyReference(propertyIdentifier=prop)
            if prop_index is not None:
                prop_ref.propertyArrayIndex = prop_index
            prop_ref_list.append(prop_ref)
            count += 1
        return (ReadAccessSpecification(objectIdentifier=(obj_type, obj_inst), listOfPropertyReferences=prop_ref_list),
                count)

    def _get_object_properties(self, point_map, target_address):
        # This will be used to get the results mapped back on the the names
        reverse_point_map = {}

        # Used to group properties together for the request.
        object_property_map = defaultdict(list)

        for name, properties in point_map.items():
            if len(properties) == 3:
                (object_type, instance_number,
                 property_name) = properties
                property_index = None
            elif len(properties) == 4:
                (object_type, instance_number, property_name,
                 property_index) = properties
            else:
                _log.error("skipping {} in request to {}: incorrect number of parameters".format(name, target_address))
                continue
            object_property_map[object_type, instance_number].append((property_name, property_index))

            reverse_point_map[object_type, instance_number, property_name, property_index] = name

        return object_property_map, reverse_point_map

    @RPC.export
    def read_properties(self, target_address, point_map, max_per_request=None, use_read_multiple=True):
        """
        Read a set of points and return the results
        """

        if not use_read_multiple:
            return self.read_using_single_request(target_address, point_map)

        # Set max_per_request really high if not set.
        if max_per_request is None:
            max_per_request = self._max_per_request

        _log.debug("Reading {count} points on {target}, max per scrape: {max}".format(
            count=len(point_map), target=target_address, max=max_per_request))
        # process point map and populate object_property_map and
        # reverse_point_map
        (object_property_map, reverse_point_map) = self._get_object_properties(point_map, target_address)

        result_dict = {}
        finished = False

        while not finished:
            read_access_spec_list = []
            count = 0
            for _ in range(max_per_request):
                try:
                    obj_data, properties = object_property_map.popitem()
                except KeyError:
                    finished = True
                    break
                (spec_list, spec_count) = self._get_access_spec(obj_data, properties)
                count += spec_count
                read_access_spec_list.append(spec_list)

            if read_access_spec_list:
                _log.debug("Requesting {count} properties from {target}".format(count=count, target=target_address))
                request = ReadPropertyMultipleRequest(listOfReadAccessSpecs=read_access_spec_list)
                request.pduDestination = Address(target_address)

                iocb = self.iocb_class(request)
                self.bacnet_application.submit_request(iocb)
                bacnet_results = iocb.ioResult.get(10)

                _log.debug("Received read response from {target} count: {count}".format(
                    count=count, target=target_address))

                for prop_tuple, value in bacnet_results.items():
                    name = reverse_point_map[prop_tuple]
                    result_dict[name] = value

        return result_dict

    @RPC.export
    def create_cov_subscription(self, address, device_path, point_name, object_type, instance_number, lifetime=None):
        """
        Called by the BACnet interface to establish a COV subscription with a
        BACnet device. IF there is an existing subscription for the point, a
        subscribeCOVRequest is sent immediately, otherwise the covIncrement
        property is confirmed to be valid before sending the subscription
        request.
        :param address: address of the device to which the subscription
        request will be sent
        :param device_path: path of the device used for the publishing topic
        :param point_name: point name for which we would like to establish the
        subscription
        :param object_type:
        :param instance_number: Arbitrarily assigned value for tracking in the
        subscription context
        :param lifetime: lifetime in seconds for the device to maintain the
        subscription
        """
        if not isinstance(address, str):
            raise RuntimeError("COV subscriptions require the address of the target device as a string")
        # if a subscription exists, send a cov subscription request
        # otherwise check the point's covIncrement
        subscription = None
        for check_sub in self.bacnet_application.sub_cov_contexts.values():
            if check_sub.point_name == point_name and \
               check_sub.monitoredObjectIdentifier == (object_type, instance_number):
                subscription = check_sub
        if subscription:
            self.send_cov_subscription(subscription.device_address,
                                       subscription.subscriberProcessIdentifier,
                                       subscription.monitoredObjectIdentifier,
                                       subscription.lifetime,
                                       subscription.point_name)
        else:
            subscription = SubscriptionContext(device_path, Address(address),
                                               point_name,
                                               object_type, instance_number,
                                               self.bacnet_application.cov_sub_process_ID,
                                               lifetime)
            # check whether the device has a usable covIncrement
            try:
                _log.debug("establishing cov subscription for point {} on device {}".format(point_name, device_path))
                self.bacnet_application.sub_cov_contexts[self.bacnet_application.cov_sub_process_ID] = subscription
                self.bacnet_application.cov_sub_process_ID += 1
                _log.debug("sending read property request for point {} on device {}".format(point_name, device_path))
                self.read_property(address, object_type, instance_number, 'covIncrement')
            except Exception as error:
                _log.warning("the covIncrement for {} on {} could not be read, no cov subscription was established".
                             format(point_name, device_path))
                _log.error(error)

    def send_cov_subscription(self, address, subscriber_process_identifier, monitored_object_identifier, lifetime,
                              point_name):
        """
        Send request to remote BACnet device to create subscription for COV on a point.
        :param address: address of the device to which the subscription
        request will be sent
        :param subscriber_process_identifier: arbitrarily set value for
        tracking cov subscriptions
        :param monitored_object_identifier: (object_type, instance_number) from
        the subscription context
        :param lifetime: lifetime in seconds for the device to maintain the
        subscription
        :param point_name:point name for which we would like to establish the
        subscription
        :return:
        """
        subscribe_cov_request = SubscribeCOVRequest(
            subscriberProcessIdentifier=subscriber_process_identifier,
            monitoredObjectIdentifier=monitored_object_identifier,
            issueConfirmedNotifications=True,
            lifetime=lifetime
        )

        subscribe_cov_request.pduDestination = address
        iocb = self.iocb_class(subscribe_cov_request)
        self.bacnet_application.submit_request(iocb)
        _log.debug("COV subscription sent to device at {} for {}".format(address, point_name))


def main(argv=sys.argv):
    """
    Main method called to start the agent.
    """
    utils.vip_main(bacnet_proxy_agent, identity="platform.bacnet_proxy", version=__version__)


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass

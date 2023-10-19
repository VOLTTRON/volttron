from __future__ import annotations

import atexit
import http
import logging
import ssl
import subprocess
import threading
import time
import xml.dom.minidom
from dataclasses import dataclass, field
from datetime import datetime
from http.client import HTTPMessage, HTTPSConnection, CannotSendRequest
from os import PathLike
from pathlib import Path
from threading import Semaphore, Timer
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4
import gevent

import ieee_2030_5.models as m
import xsdata
from blinker import Signal
from ieee_2030_5 import dataclass_to_xml, xml_to_dataclass

_log = logging.getLogger(__name__)
_log_req_resp = logging.getLogger(f"{__name__}.req_resp")

TimeType = int
StrPath = Union[str, Path]


@dataclass
class TimerSpec:
    trigger_after_seconds: int
    fn: Callable
    args: List = field(default_factory=list)
    kwargs: Dict = field(default_factory=dict)
    enabled: bool = True
    trigger_count: int = 0
    last_trigger_time: int = int(time.mktime(datetime.utcnow().timetuple()))

    def disable(self):
        self.enabled = False

    def enable(self):
        self.enabled = True

    def reset_count(self):
        self.trigger_count = 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TimerSpec):
            raise NotImplementedError(
                f"Comparison between {self.__class__.__name__} and {type(other)} not implemented")
        return self.fn is other.fn

    def trigger(self, current_time: int):
        if self.last_trigger_time + self.trigger_after_seconds < current_time:
            if self.args and self.kwargs:
                self.fn(args=self.args, kwargs=self.kwargs)
            elif self.args:
                self.fn(args=self.args)
            else:
                self.fn()
            self.trigger_count += 1
            self.last_trigger_time = current_time


class _TimerThread(gevent.Greenlet):
    tick = Signal("tick")

    def __init__(self):
        super().__init__()
        self._tick = 0

    @staticmethod
    def user_readable(timestamp: int):
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%m/%d/%Y, %H:%M:%S")

    def run(self) -> None:

        while True:
            self._tick = int(time.mktime(datetime.utcnow().timetuple()))
            _TimerThread.tick.send(self._tick)
            time.sleep(1)


TimerThread = _TimerThread()
TimerThread.daemon = True
TimerThread.start()


class IEEE2030_5_Client:
    clients: set[IEEE2030_5_Client] = set()

    # noinspection PyUnresolvedReferences
    def __init__(self,
                 cafile: StrPath,
                 server_hostname: str,
                 keyfile: StrPath,
                 certfile: StrPath,
                 pin: str,
                 server_ssl_port: Optional[int] = 443,
                 debug: bool = True,
                 device_capabilities_endpoint: str = "/dcap",
                 log_req_resp: bool = True):

        self._cafile: Path = cafile if isinstance(cafile, Path) else Path(cafile)
        self._keyfile: Path = keyfile if isinstance(keyfile, Path) else Path(keyfile)
        self._certfile: Path = certfile if isinstance(certfile, Path) else Path(certfile)

        self._pin = pin

        # We know that these are Path objects now and have a .exists() function based upon above code.
        assert self._cafile.exists(
        ), f"cafile doesn't exist ({cafile})"    # type: ignore[attr-defined]
        assert self._keyfile.exists(
        ), f"keyfile doesn't exist ({keyfile})"    # type: ignore[attr-defined]
        assert self._certfile.exists(
        ), f"certfile doesn't exist ({certfile})"    # type: ignore[attr-defined]

        self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_REQUIRED
        self._ssl_context.load_verify_locations(cafile=cafile)

        # Loads client information from the passed cert and key files. For
        # client side validation.
        self._ssl_context.load_cert_chain(certfile=certfile, keyfile=keyfile)

        self._http_conn = HTTPSConnection(host=server_hostname,
                                          port=server_ssl_port,
                                          context=self._ssl_context)
        self._response_headers: HTTPMessage
        self._response_status = None
        self._debug = debug
        self._debug = log_req_resp
        if not self._debug:
            _log_req_resp.setLevel(logging.WARNING)

        self._mup: m.MirrorUsagePointList = None    # type: ignore
        self._upt: m.UsagePointList = None    # type: ignore

        self._dcap_poll_rate: int = 0
        self._dcap_timer: Optional[Timer] = None
        self._disconnect: bool = False

        self._timer_specs: Dict[str, TimerSpec] = {}

        # Offset between local udt and server udt
        self._time_offset: int = 0

        self._end_device_map: Dict[str, m.EndDeviceList] = {}
        self._end_devices: Dict[str, m.EndDevice] = {}

        self._fsa_map: Dict[str, m.FunctionSetAssignmentsList] = {}
        self._fsa: Dict[str, m.FunctionSetAssignments] = {}

        self._der_map: Dict[str, m.DERList] = {}
        self._der: Dict[str, m.DER] = {}

        self._der_program_map: Dict[str, m.DERProgramList] = {}
        self._der_program: Dict[str, m.DERProgram] = {}

        self._mirror_usage_point_map: Dict[str, m.MirrorUsagePointList] = {}
        self._mirror_usage_point: Dict[str, m.MirrorUsagePoint] = {}

        self._usage_point_map: Dict[str, m.UsagePointList] = {}
        self._usage_point: Dict[str, m.UsagePoint] = {}

        self._before_dcap_update_signal = Signal('before-dcap-request')
        self._after_dcap_update_signal = Signal('before-dcap-request')
        self._before_client_start_signal = Signal('before-client-start')
        self._after_client_start_signal = Signal('after-client-start')

        self._der_control_event_started_signal = Signal('der-control-event-started')
        self._der_control_event_ended_signal = Signal('der-control-event-ended')

        self._default_control_changed = Signal("default-control-changed")

        self._dcap_endpoint = device_capabilities_endpoint

        self._der_default_control: m.DefaultDERControl = m.DefaultDERControl()
        self._der_active_controls: m.DERControlList = m.DERControlList()

        self._config: Dict[str, Any] = {}
        self._lock = Semaphore()

        IEEE2030_5_Client.clients.add(self)

    def start(self, config: Dict[str, Any]):
        """Starts the client connection to the 2030.5 server configured during construction.
        """
        self._config = config
        self._before_client_start_signal.send(self)
        self._update_dcap_tree()
        self._after_client_start_signal.send(self)
        TimerThread.tick.connect(self._tick)

    def _tick(self, timestamp: int):
        """Handles the timer event thread for the client.

        :param timestamp: The current timestamp
        :type timestamp: int
        """
        if self._lock.acquire(blocking=False):
            for ts in self._timer_specs.values():
                ts.trigger(timestamp)
            self._lock.release()

    def der_default_control_changed(self, fun: Callable):
        self._default_control_changed.connect(fun)

    def der_control_event_started(self, fun: Callable):
        self._der_control_event_started_signal.connect(fun)

    def der_control_event_ended(self, fun: Callable):
        self._der_control_event_ended_signal.connect(fun)

    def before_dcap_update(self, fun: Callable):
        self._before_dcap_update_signal.connect(fun)

    def after_dcap_update(self, fun: Callable):
        self._after_dcap_update_signal.connect(fun)

    def after_client_start(self, fun: Callable):
        self._after_client_start_signal.connect(fun)

    def before_client_start(self, fun: Callable):
        self._before_client_start_signal.connect(fun)

    @property
    def server_time(self) -> TimeType:
        """Returns the time on the server
        
        Uses an offset value from the 2030.5 Time function set to determine the
        current time on the server.  

        :return: A calculated server_time including offset from time endpoint
        :rtype: TimeType
        """
        return int(time.mktime(datetime.utcnow().timetuple())) + self._time_offset

    def get_der_hrefs(self) -> List[str]:
        return list(self._der.keys())

    def get_der(self, href: str) -> Optional[m.DER]:
        return self._der.get(href)

    def get_der_list(self, href: Optional[str] = None) -> m.DERList:
        if href is None:
            href = self.enddevice.DERListLink.href
        resp = self.__get_request__(href)
        return self._der_map.get(href)

    def put_der_availability(self, der_href: str, new_availability: m.DERAvailability) -> int:
        resp = self.__put__(der_href, dataclass_to_xml(new_availability))
        return resp.status

    def put_der_capability(self, new_capability: m.DERCapability) -> int:
        resp = self.__put__(
            list(self._der.values())[0].DERCapabilityLink, dataclass_to_xml(new_capability))
        return resp.status

    def put_der_settings(self, new_settings: m.DERSettings) -> int:
        resp = self.__put__(
            list(self._der.values())[0].DERSettingsLink.href, dataclass_to_xml(new_settings))
        return resp.status

    def put_der_status(self, new_status: m.DERStatus) -> int:
        if not isinstance(new_status.operationalModeStatus, m.OperationalModeStatusType):
            new_status.operationalModeStatus = m.OperationalModeStatusType(
                self.server_time, value=new_status.operationalModeStatus)

        resp = self.__put__(
            list(self._der.values())[0].DERStatusLink.href, dataclass_to_xml(new_status))
        return resp.status

    def _send_control_events(self, der_program_href: str):
        # Need to check this every 10 seconds for updates to conttrols
        program: m.DERProgram = self.__get_request__(der_program_href)

        active: m.DERControlList = self.__get_request__(program.ActiveDERControlListLink.href)
        default = self.__get_request__(program.DefaultDERControlLink.href)
        active_is_different = False

        to_add = []
        for newderctl in active.DERControl:
            found = False
            for existingctl in self._der_active_controls.DERControl:
                if existingctl.mRID == newderctl.mRID:
                    found = True
                    if existingctl == newderctl:
                        _log.debug(f"Currently in event {newderctl.mRID}")
                    else:
                        _log.debug(
                            "TODO ->>>>>>>>>>>>>>>>>>>>>>>>>>> Existing mRID should superscede????"
                        )
                    break
            if not found:
                to_add.append(newderctl)

        for ctrl in to_add:
            self._der_control_event_started_signal.send(ctrl)

        to_remove = []
        for existingctl in self._der_active_controls.DERControl:
            found = False
            for newctrl in active.DERControl:
                if newctrl.mRID == existingctl.mRID:
                    found = True
                    break
            if not found:
                to_remove.append(existingctl)

        i = len(self._der_active_controls.DERControl)
        while i > 0:
            i -= 1
            if self._der_active_controls.DERControl[i] in to_remove:
                self._der_control_event_ended_signal.send(self._der_active_controls.DERControl[i])
                self._der_active_controls.DERControl.pop(i)

        self._der_active_controls = active

        if default != self._der_default_control:
            self._der_default_control = default
            _log.debug("Default control changed....")
            self._default_control_changed.send(default)

        # Poll every 60 if default otherwise use setting in config file.
        refresh_time = self._config.get("default_der_control_poll", 60)
        self._update_timer_spec("der_control_event",
                                refresh_time,
                                fn=lambda: self._send_control_events(der_program_href))

    def _update_dcap_tree(self, endpoint: Optional[str] = None):
        """Retrieve device capability 

        :param endpoint: _description_, defaults to None
        :type endpoint: Optional[str], optional
        :raises ValueError: _description_
        :raises RuntimeError: _description_
        :raises ValueError: _description_
        """
        if not endpoint:
            endpoint = self._dcap_endpoint
            if not endpoint:
                raise ValueError("Invalid device_capability_endpoint specified in constructor.")

        self._before_dcap_update_signal.send(self)

        # retrieve device capabilities from the server
        dcap: m.DeviceCapability = self.__get_request__(endpoint)
        if self._response_status != 200:
            raise RuntimeError(dcap)

        self._after_dcap_update_signal.send(self)

        if dcap.pollRate is None:
            dcap.pollRate = 900

        self._update_timer_spec("dcap", dcap.pollRate, self._update_dcap_tree)

        # if time is available then grab and create an offset
        if dcap.TimeLink is not None and dcap.TimeLink.href:
            _time: m.Time = self.__get_request__(dcap.TimeLink.href)
            self._time_offset = int(time.mktime(datetime.utcnow().timetuple())) - _time.currentTime

        if dcap.EndDeviceListLink is not None and dcap.EndDeviceListLink.all > 0:

            self._update_list(dcap.EndDeviceListLink.href, "EndDevice", self._end_device_map,
                              self._end_devices)

            for ed in self._end_devices.values():

                if not self.is_end_device_registered(ed, self._pin):
                    raise ValueError(f"Device is not registered on this server!")
                self._update_list(ed.FunctionSetAssignmentsListLink.href, "FunctionSetAssignments",
                                  self._fsa_map, self._fsa)

                if ed.DERListLink:
                    derlist: m.DERList = self.__get_request__(ed.DERListLink.href)
                    self._der_map[derlist.href] = derlist
                    for index, der in enumerate(derlist.DER):
                        self._der[der.href] = der

                    if derlist.DER[0].CurrentDERProgramLink:
                        self._send_control_events(derlist.DER[0].CurrentDERProgramLink.href)

            for fsa in self._fsa.values():
                if fsa.DERProgramListLink:
                    self._der_program_map[fsa.DERProgramListLink.href] = self.__get_request__(
                        fsa.DERProgramListLink.href)
                    program = self._der_program_map[fsa.DERProgramListLink.href]

        if dcap.MirrorUsagePointListLink is not None and dcap.MirrorUsagePointListLink.href:
            self._update_list(dcap.MirrorUsagePointListLink.href, "MirrorUsagePoint",
                              self._mirror_usage_point_map, self._mirror_usage_point)

        self._dcap = dcap

    def _update_timer_spec(self, spec_name: str, rate: int, fn: Callable, *args, **kwargs):
        ts = self._timer_specs.get(spec_name)
        if ts is None:
            ts = self._timer_specs[spec_name] = TimerSpec(rate, fn, args, kwargs)
        ts.trigger_after_seconds = rate

    def post_log_event(self, end_device: m.EndDevice, log_event: m.LogEvent):
        if not log_event.createdDateTime:
            log_event.createdDateTime = self.server_time

        self.request(end_device.LogEventListLink.href, method="POST")

    def _update_list(self, path: str, list_prop: str, outer_map: Dict, inner_map: Dict):
        """Update mappings using 2030.5 list nomoclature.
        
        Example structure for EndDeviceListLink
        
            EndDeviceListLink.href points to EndDeviceList.
            EndDeviceList.EndDevice points to a list of EndDevice objects.
            
        Args:
        
            path: Original path of the list (in example EndDeviceListLink.href)
            list_prop: The property on the object that holds a list of elements (in example EndDevice)
            outer_mapping: Mapping where the original list object is stored by href
            inner_mapping: Mapping where the inner objects are stored by href
        
        """
        my_response = self.__get_request__(path)

        if self._response_status != 200:
            raise RuntimeError(my_response)

        if my_response is not None:
            href = getattr(my_response, "href")
            outer_map[href] = my_response
            for inner in getattr(my_response, list_prop):
                href = getattr(inner, "href")
                inner_map[href] = inner

    def _get_device_capabilities(self, endpoint: str) -> m.DeviceCapability:
        dcap: m.DeviceCapability = self.__get_request__(endpoint)
        if self._response_status != 200:
            raise RuntimeError(dcap)

        self._dcap = dcap

        if self._device_cap.pollRate is not None:
            self._dcap_poll_rate = self._device_cap.pollRate
        else:
            self._dcap_poll_rate = 600

        self._dcap_timer = Timer(self._dcap_poll_rate, self.poll_timer,
                                 (self.device_capability, url))
        self._dcap_timer.start()

        return self._device_cap

    @property
    def lfdi(self) -> str:
        cmd = ["openssl", "x509", "-in", str(self._certfile), "-noout", "-fingerprint", "-sha256"]
        ret_value = subprocess.check_output(cmd, text=True)
        if "=" in ret_value:
            ret_value = ret_value.split("=")[1].strip()

        fp = ret_value.replace(":", "")
        lfdi = fp[:40]
        return lfdi

    @property
    def http_conn(self) -> HTTPSConnection:
        if self._http_conn.sock is None:
            self._http_conn.connect()
        return self._http_conn

    @property
    def enddevices(self) -> m.EndDeviceList:
        return self._end_devices

    @property
    def enddevice(self, href: str = "") -> m.EndDevice:
        """Retrieve a client's end device based upon the href of the end device.
        
        Args:
        
            href: If "" then in single client mode and return the only end device available.
        """
        if not href:
            href = list(self._end_devices.keys())[0]

        end_device = self._end_devices.get(href)

        return end_device

    def __hash__(self) -> int:
        return self._keyfile.read_text().__hash__()    # type: ignore[attr-defined]

    def is_end_device_registered(self, end_device: m.EndDevice, pin: int) -> bool:
        reg = self.registration(end_device)
        return reg.pIN == self._pin

    def new_uuid(self, url: str = "/uuid") -> str:
        res = self.__get_request__(url)
        return res

    def get_enddevices(self) -> m.EndDeviceList:
        return self.__get_request__(self._device_cap.EndDeviceListLink.href)

    def end_device(self, index: Optional[int] = 0) -> m.EndDevice:
        if not self._end_devices:
            self.end_devices()

        return self._end_devices.EndDevice[index]

    def self_device(self) -> m.EndDevice:
        if not self._device_cap:
            self.device_capability()

        return self.__get_request__(self._device_cap.SelfDeviceLink.href)

    def function_set_assignment(self) -> m.FunctionSetAssignmentsListLink:
        fsa_list = self.__get_request__(self.end_device().FunctionSetAssignmentsListLink.href)
        return fsa_list

    def poll_timer(self, fn, args):
        if not self._disconnect:
            _log.debug(threading.currentThread().name)
            fn(args)
            threading.currentThread().join()

    def device_capability(self, url: str = "/dcap") -> m.DeviceCapability:
        self._device_cap: m.DeviceCapability = self.__get_request__(url)
        if self._device_cap.pollRate is not None:
            self._dcap_poll_rate = self._device_cap.pollRate
        else:
            self._dcap_poll_rate = 600

        _log.debug(f"devcap id {id(self._device_cap)}")
        _log.debug(threading.currentThread().name)
        _log.debug(f"DCAP: Poll rate: {self._dcap_poll_rate}")
        self._dcap_timer = Timer(self._dcap_poll_rate, self.poll_timer,
                                 (self.device_capability, url))
        self._dcap_timer.start()

        return self._device_cap

    def time(self) -> m.Time:
        timexml = self.__get_request__(self._device_cap.TimeLink.href)
        return timexml

    def der_program_list(self, device: m.EndDevice) -> m.DERProgramList:
        fsa: m.FunctionSetAssignments = self.__get_request__(
            device.FunctionSetAssignmentsListLink.href)
        der_programs_list: m.DERProgramList = self.__get_request__(fsa.DERProgramListLink.href)

        return der_programs_list

    def post_mirror_reading(self, reading: m.MirrorMeterReading) -> str:
        data = dataclass_to_xml(reading)
        resp = self.__post__(reading.href, data=data)

        if not int(resp.status) >= 200 and int(resp.status) < 300:
            _log.error(f"Posting to {reading.href}")
            _log.error(f"Response status: {resp.status}")
            _log.error(f"{resp.read().decode('utf-8')}")

        return resp.headers['Location']

    def mirror_usage_point_list(self) -> m.MirrorUsagePointList:
        mupl = self._mirror_usage_point_map.get(self._dcap.MirrorUsagePointListLink.href)

        return mupl

    def usage_point_list(self) -> m.UsagePointList:
        self._upt = self.__get_request__(self._device_cap.UsagePointListLink.href)
        return self._upt

    def registration(self, end_device: m.EndDevice) -> m.Registration:
        reg = self.__get_request__(end_device.RegistrationLink.href)
        return reg

    def timelink(self):
        if self._device_cap is None:
            raise ValueError("Request device capability first")
        return self.__get_request__(url=self._device_cap.TimeLink.href)

    def disconnect(self):
        self._disconnect = True
        self._dcap_timer.cancel()
        IEEE2030_5_Client.clients.remove(self)

    def request(self, endpoint: str, body: dict = {}, method: str = "GET", headers: dict = {}):

        if method.upper() == 'GET':
            return self.__get_request__(endpoint, body, headers=headers)

        if method.upper() == 'POST':
            return self.__post__(endpoint, body, headers=headers)

    def create_mirror_usage_point(self, mirror_usage_point: m.MirrorUsagePoint) -> str:
        """Create a new mirror usage point on the server.
        
        Args:
        
            mirror_usage_point: Minimal type for MirrorUsagePoint
            
        Return:
        
            The location of the new usage point href for posting to.
        """
        data = dataclass_to_xml(mirror_usage_point)
        resp = self.__post__(self._dcap.MirrorUsagePointListLink.href, data=data)
        return resp.headers['Location']

    def __put__(self, url: str, data: Any, headers: Optional[Dict[str, str]] = None):
        if not headers:
            headers = {'Content-Type': 'text/xml'}

        if self._debug:
            _log_req_resp.debug(f"----> PUT REQUEST\nurl: {url}\nbody: {data}")

        try:
            self.http_conn.request(method="PUT", headers=headers, url=url, body=data)
        except http.client.CannotSendRequest as ex:
            self.http_conn.close()
            _log.debug("Reconnecting to server")
            self.http_conn.request(method="PUT", headers=headers, url=url, body=data)

        response = self._http_conn.getresponse()
        return response

    def __post__(self, url: str, data=None, headers: Optional[Dict[str, str]] = None):
        if not headers:
            headers = {'Content-Type': 'text/xml'}

        if self._debug:
            _log_req_resp.debug(f"----> POST REQUEST\nurl: {url}\nbody: {data}")

        self.http_conn.request(method="POST", headers=headers, url=url, body=data)
        response = self._http_conn.getresponse()
        response_data = response.read().decode("utf-8")
        # response_data = response.read().decode("utf-8")
        if response_data and self._debug:
            _log_req_resp.debug(f"<---- POST RESPONSE\n{response_data}")

        return response

    def __get_request__(self, url: str, body=None, headers: Optional[Dict] = None):
        if headers is None:
            headers = {"Connection": "keep-alive", "keep-alive": "timeout=30, max=1000"}

        if self._debug:
            _log_req_resp.debug(f"----> GET REQUEST\nurl: {url}\nbody: {body}")
        try:
            self.http_conn.request(method="GET", url=url, body=body, headers=headers)
        except http.client.CannotSendRequest as ex:
            self.http_conn.close()
            _log.debug("Reconnecting to server")
            self.http_conn.request(method="GET", url=url, body=body, headers=headers)

        response = self._http_conn.getresponse()
        response_data = response.read().decode("utf-8")
        self._response_headers = response.headers
        self._response_status = response.status

        response_obj = None
        try:
            response_obj = xml_to_dataclass(response_data)
            resp_xml = xml.dom.minidom.parseString(response_data)
            if resp_xml and self._debug:
                _log_req_resp.debug(f"<---- GET RESPONSE\n{response_data}")    # toprettyxml()}")

        except xsdata.exceptions.ParserError as ex:
            if self._debug:
                _log_req_resp.debug("<---- GET RESPONSE\n{response_data}")
            response_obj = response_data

        return response_obj

    def __close__(self):
        self._http_conn.close()
        self._ssl_context = None
        self._http_conn = None


# noinspection PyTypeChecker
def __release_clients__():
    for x in IEEE2030_5_Client.clients:
        x.__close__()
    IEEE2030_5_Client.clients = None


atexit.register(__release_clients__)

# if __name__ == '__main__':
#     SERVER_CA_CERT = Path("~/tls/certs/ca.crt").expanduser().resolve()
#     KEY_FILE = Path("~/tls/private/dev1.pem").expanduser().resolve()
#     CERT_FILE = Path("~/tls/certs/dev1.crt").expanduser().resolve()

    #     headers = {'Connection': 'Keep-Alive', 'Keep-Alive': "max=1000,timeout=30"}

    #     h = IEEE_2030_5_Client(cafile=SERVER_CA_CERT,
    #                            server_hostname="127.0.0.1",
    #                            server_ssl_port=8070,
    #                            keyfile=KEY_FILE,
    #                            certfile=CERT_FILE,
    #                            debug=True)
    #     # h2 = IEEE2030_5_Client(cafile=SERVER_CA_CERT, server_hostname="me.com", ssl_port=8000,
    #     #                        keyfile=KEY_FILE, certfile=KEY_FILE)
    #     dcap = h.device_capability()
    #     end_devices = h.end_devices()

    #     if not end_devices.all > 0:
    #         print("registering end device.")
    #         ed_href = h.register_end_device()
    #     my_ed = h.end_devices()

    #     # ed = h.end_devices()[0]
    #     # resp = h.request("/dcap", headers=headers)
    #     # print(resp)
    #     # resp = h.request("/dcap", headers=headers)
    #     # print(resp)
    #     #dcap = h.device_capability()
    #     # get device list
    #     #dev_list = h.request(dcap.EndDeviceListLink.href).EndDevice

    #     #ed = h.request(dev_list[0].href)
    #     #print(ed)
    #     #
    #     # print(dcap.mirror_usage_point_list_link)
    #     # # print(h.request(dcap.mirror_usage_point_list_link.href))
    #     # print(h.request("/dcap", method="post"))

    #     # tl = h.timelink()
    #     #print(IEEE2030_5_Client.clients)

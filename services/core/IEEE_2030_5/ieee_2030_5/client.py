from __future__ import annotations

import atexit
import logging
import ssl
import subprocess
import threading
import xml.dom.minidom
from http.client import HTTPMessage, HTTPSConnection
from os import PathLike
from pathlib import Path
from threading import Timer
from typing import Dict, Optional, Tuple
from uuid import uuid4

import ieee_2030_5.models as m
import xsdata
from ieee_2030_5 import dataclass_to_xml, xml_to_dataclass

_log = logging.getLogger(__name__)


class IEEE2030_5_Client:
    clients: set[IEEE2030_5_Client] = set()

    # noinspection PyUnresolvedReferences
    def __init__(self,
                 cafile: PathLike,
                 server_hostname: str,
                 keyfile: PathLike,
                 certfile: PathLike,
                 pin: str,
                 server_ssl_port: Optional[int] = 443,
                 debug: bool = True):

        cafile = cafile if isinstance(cafile, PathLike) else Path(cafile)
        keyfile = keyfile if isinstance(keyfile, PathLike) else Path(keyfile)
        certfile = certfile if isinstance(certfile, PathLike) else Path(certfile)

        self._keyfile = keyfile
        self._certfile = certfile
        self._cafile = cafile
        self._pin = pin

        # We know that these are Path objects now and have a .exists() function based upon above code.
        assert cafile.exists(), f"cafile doesn't exist ({cafile})" # type: ignore[attr-defined]
        assert keyfile.exists(), f"keyfile doesn't exist ({keyfile})"  # type: ignore[attr-defined]
        assert certfile.exists(), f"certfile doesn't exist ({certfile})"  # type: ignore[attr-defined]

        self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_OPTIONAL  #  ssl.CERT_REQUIRED
        self._ssl_context.load_verify_locations(cafile=cafile)

        # Loads client information from the passed cert and key files. For
        # client side validation.
        self._ssl_context.load_cert_chain(certfile=certfile, keyfile=keyfile)

        self._http_conn = HTTPSConnection(host=server_hostname,
                                          port=server_ssl_port,
                                          context=self._ssl_context)
        self._response_headers: HTTPMessage
        self._response_status = None
        
        self._device_cap: m.DeviceCapability = m.DeviceCapability()
        self._mup: m.MirrorUsagePointList = m.MirrorUsagePointList()
        self._upt: m.UsagePointList = m.UsagePointList()
        self._edev: m.EndDeviceListLink = m.EndDeviceListLink()
        self._end_devices: m.EndDeviceList = m.EndDeviceList()
        self._fsa_list: m.FunctionSetAssignmentsList = m.FunctionSetAssignmentsList()
        self._der_programs: m.DERProgramList = m.DERProgramList()
        self._mup: m.MirrorUsagePoint = m.MirrorUsagePoint()
        self._debug = debug
        self._dcap_poll_rate: int = 0
        self._dcap_timer: Optional[Timer] = None
        self._disconnect: bool = False
    
        # Starts a timer
        self.update_state()

        IEEE2030_5_Client.clients.add(self)
        
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
    def enddevice(self, index: int = 0) -> m.EndDevice:
        return self._end_devices.EndDevice[index]
        
    
    def __hash__(self) -> int:
        return self._keyfile.read_text().__hash__() # type: ignore[attr-defined]
    
    
    def update_state(self) -> None:
        self._device_cap = self.device_capability()
        self._end_devices = self.get_enddevices()
        ed = self.enddevice
        if ed.FunctionSetAssignmentsListLink.href:
            self._fsa_list: m.FunctionSetAssignmentsList = self.request(endpoint=ed.FunctionSetAssignmentsListLink.href)
            if len(self._fsa_list.FunctionSetAssignments) > 1:
                raise ValueError("Server responded with more than one function set assignment.")
            for fsa in self._fsa_list.FunctionSetAssignments:
                if fsa.DERProgramListLink.href:
                    self._der_programs = self.request(fsa.DERProgramListLink.href)
                
            

    # def register_end_device(self) -> str:
    #     lfid = utils.get_lfdi_from_cert(self._cert)
    #     sfid = utils.get_sfdi_from_lfdi(lfid)
    #     response = self.__post__(dcap.EndDeviceListLink.href,
    #                              data=utils.dataclass_to_xml(
    #                                  m.EndDevice(sFDI=sfid)))
    #     print(response)

    #     if response.status in (200, 201):
    #         return response.headers.get("Location")

    #     raise werkzeug.exceptions.Forbidden()

    def is_end_device_registered(self, end_device: m.EndDevice,
                                 pin: int) -> bool:
        reg = self.registration(end_device)
        return reg.pIN == pin

    def new_uuid(self, url: str = "/uuid") -> str:
        res = self.__get_request__(url)
        return res
    
    def get_enddevices(self) -> m.EndDeviceList:
        return self.__get_request__(self._device_cap.EndDeviceListLink.href)

    # def end_devices(self) -> m.EndDeviceList:
    #     self._end_devices = self.__get_request__(self._device_cap.EndDeviceListLink.href)
    #     return self._end_devices

    def end_device(self, index: Optional[int] = 0) -> m.EndDevice:
        if not self._end_devices:
            self.end_devices()

        return self._end_devices.EndDevice[index]

    def self_device(self) -> m.EndDevice:
        if not self._device_cap:
            self.device_capability()

        return self.__get_request__(self._device_cap.SelfDeviceLink.href)

    def function_set_assignment(self) -> m.FunctionSetAssignmentsListLink:
        fsa_list = self.__get_request__(
            self.end_device().FunctionSetAssignmentsListLink.href)
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
        self._dcap_timer = Timer(self._dcap_poll_rate, self.poll_timer, (self.device_capability, url))
        self._dcap_timer.start()
        
        return self._device_cap

    def time(self) -> m.Time:
        timexml = self.__get_request__(self._device_cap.TimeLink.href)
        return timexml

    def der_program_list(self, device: m.EndDevice) -> m.DERProgramList:
        fsa: m.FunctionSetAssignments = self.__get_request__(
            device.FunctionSetAssignmentsListLink.href)
        der_programs_list: m.DERProgramList = self.__get_request__(
            fsa.DERProgramListLink.href)

        return der_programs_list

    def post_mirror_reading(self, reading: m.MirrorMeterReading):
        print(reading)
        
    def mirror_usage_point_list(self) -> m.MirrorUsagePointList:
        self._mup = self.__get_request__(
            self._device_cap.MirrorUsagePointListLink.href)
        return self._mup

    def usage_point_list(self) -> m.UsagePointList:
        self._upt = self.__get_request__(
            self._device_cap.UsagePointListLink.href)
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

    def request(self,
                endpoint: str,
                body: dict = None,
                method: str = "GET",
                headers: dict = None):

        if method.upper() == 'GET':
            return self.__get_request__(endpoint, body, headers=headers)

        if method.upper() == 'POST':
            print("Doing post")
            return self.__post__(endpoint, body, headers=headers)

    def create_mirror_usage_point(
            self, mirror_usage_point: m.MirrorUsagePoint) -> Tuple[int, str]:
        data = dataclass_to_xml(mirror_usage_point)
        resp = self.__post__(self._device_cap.MirrorUsagePointListLink.href,
                             data=data)
        return resp.status, resp.headers['Location']

    def __post__(self,
                 url: str,
                 data=None,
                 headers: Optional[Dict[str, str]] = None):
        if not headers:
            headers = {'Content-Type': 'text/xml'}

        self.http_conn.request(method="POST",
                               headers=headers,
                               url=url,
                               body=data)
        response = self._http_conn.getresponse()
        # response_data = response.read().decode("utf-8")

        return response

    def __get_request__(self, url: str, body=None, headers: Optional[Dict] = None):
        if headers is None:
            headers = {
                "Connection": "keep-alive",
                "keep-alive": "timeout=30, max=1000"
            }

        if self._debug:
            print(f"----> GET REQUEST")
            print(f"url: {url} body: {body}")
        self.http_conn.request(method="GET",
                               url=url,
                               body=body,
                               headers=headers)
        
        response = self._http_conn.getresponse()
        response_data = response.read().decode("utf-8")
        self._response_headers = response.headers
        self._response_status = response.status

        response_obj = None
        try:
            response_obj = xml_to_dataclass(response_data)
            resp_xml = xml.dom.minidom.parseString(response_data)
            if resp_xml and self._debug:
                print(f"<---- GET RESPONSE")
                print(f"{response_data}")  # toprettyxml()}")

        except xsdata.exceptions.ParserError as ex:
            if self._debug:
                print(f"<---- GET RESPONSE")
                print(f"{response_data}")
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

#
# ssl_context = ssl.create_default_context(cafile=str(SERVER_CA_CERT))
#
#
# con = HTTPSConnection("me.com", 8000,
#                       key_file=str(KEY_FILE),
#                       cert_file=str(CERT_FILE),
#                       context=ssl_context)
# con.request("GET", "/dcap")
# print(con.getresponse().read())
# con.close()

if __name__ == '__main__':
    SERVER_CA_CERT = Path("~/tls/certs/ca.crt").expanduser().resolve()
    KEY_FILE = Path("~/tls/private/dev1.pem").expanduser().resolve()
    CERT_FILE = Path("~/tls/certs/dev1.crt").expanduser().resolve()

    headers = {'Connection': 'Keep-Alive', 'Keep-Alive': "max=1000,timeout=30"}

    h = IEEE2030_5_Client(cafile=SERVER_CA_CERT,
                          server_hostname="127.0.0.1",
                          server_ssl_port=8070,
                          keyfile=KEY_FILE,
                          certfile=CERT_FILE,
                          debug=True)
    # h2 = IEEE2030_5_Client(cafile=SERVER_CA_CERT, server_hostname="me.com", ssl_port=8000,
    #                        keyfile=KEY_FILE, certfile=KEY_FILE)
    dcap = h.device_capability()
    end_devices = h.end_devices()

    if not end_devices.all > 0:
        print("registering end device.")
        ed_href = h.register_end_device()
    my_ed = h.end_devices()

    # ed = h.end_devices()[0]
    # resp = h.request("/dcap", headers=headers)
    # print(resp)
    # resp = h.request("/dcap", headers=headers)
    # print(resp)
    #dcap = h.device_capability()
    # get device list
    #dev_list = h.request(dcap.EndDeviceListLink.href).EndDevice

    #ed = h.request(dev_list[0].href)
    #print(ed)
    #
    # print(dcap.mirror_usage_point_list_link)
    # # print(h.request(dcap.mirror_usage_point_list_link.href))
    # print(h.request("/dcap", method="post"))

    # tl = h.timelink()
    #print(IEEE2030_5_Client.clients)

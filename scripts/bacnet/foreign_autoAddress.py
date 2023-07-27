#!/usr/bin/env python

import csv
import json
import os
import pprint
import socket
import subprocess
import sys
import threading
import traceback
from collections import defaultdict
# import inspect
# import ipaddress
# import netifaces as ni
from datetime import datetime
from queue import Empty, Queue
from time import sleep, time

import requests
from bacpypes.apdu import (PropertyReference, ReadAccessSpecification,
                           ReadPropertyACK, ReadPropertyMultipleACK,
                           ReadPropertyMultipleRequest, ReadPropertyRequest,
                           WhoIsRequest)
from bacpypes.app import BIPSimpleApplication, BIPForeignApplication
from bacpypes.consolelogging import ConfigArgumentParser
from bacpypes.constructeddata import Array
from bacpypes.core import enable_sleeping, run, stop
from bacpypes.debugging import ModuleLogger, bacpypes_debugging
from bacpypes.errors import MissingRequiredParameter
from bacpypes.iocb import IOCB
from bacpypes.object import get_datatype
from bacpypes.pdu import Address, GlobalBroadcast
from bacpypes.primitivedata import Unsigned
from bacpypes.service.device import LocalDeviceObject
from bacpypes.task import OneShotDeleteTask, RecurringFunctionTask

_debug = 1
__version__ = "0.2.0"
_log = ModuleLogger(globals())


class NetworkProperties(dict):
    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            value = self[item] = type(self)()
            return value


def OneShotDelayFunction(delay, fn, *args, **kwargs):
    class OneShotFunctionTask(OneShotDeleteTask):
        def process_task(self):
            fn(*args, **kwargs)

    task = OneShotFunctionTask()

    task.install_task(when=(delay + time()))

    return task


class ScanConfigParser(ConfigArgumentParser):
    def __init__(self, **kwargs):
        ConfigArgumentParser.__init__(self, **kwargs)

        self.add_argument(
            "--ewebcsv", help="path to processed topic list from enteliweb"
        )

        self.add_argument("--devicecsv", help="path to device list")

        self.add_argument("--visualbacnetcsv", help="path to device list")

        self.add_argument(
            "--retrieve_configs", action="store_true", help="get configs from database"
        )

        self.add_argument(
            "--timeout",
            default=60,
            type=int,
            help="time to wait for whois responses after last request"
            " default is 60 seconds",
        )

        self.add_argument(
            "--show_dead",
            action="store_true",
            help="only show devices not responding to whois",
        )

        self.add_argument(
            "--building_name",
            help="set authoritative building name to be used to build devices",
            required=True,
        )

        self.add_argument(
            "--client_name", help="set authoritative client name", required=True
        )

        self.add_argument(
            "--install_matched",
            action="store_true",
            help="install devices and registries in the local volttron",
        )

        self.add_argument(
            "--print_devices", action="store_true", help="print devices as found"
        )

        self.add_argument(
            "--retrieve_devices", action="store_true", help="process devices in cache"
        )

        self.add_argument(
            "--store_devices", action="store_true", help="save found devices to cache"
        )

        self.add_argument(
            "--scan_devices",
            action="store_true",
            help="scan devices listed in provided csv",
        )

        self.add_argument("--whois_address", help="address to send whois request to")
        self.add_argument(
            "--scan_bacnet", action="store_true", help="scan network for devices"
        )

        self.add_argument("--scan_high_limit", help="Whois High Limit device ID")

        self.add_argument("--scan_low_limit", help="Whois Low Limit device ID")

        self.add_argument("--scan_device", help="scan device for points")

        self.add_argument(
            "--read_properties", action="store_true", help="query device properties"
        )

        self.add_argument("--readpropsdev", help="device to read properties from")

        self.add_argument("--readpropsadd", help="address to read properties from")

        self.add_argument(
            "--print_properties", action="store_true", help="print device properties"
        )

        self.add_argument(
            "--save_properties_csv",
            action="store_true",
            help="save device properties to csv",
        )

        self.add_argument(
            "--upload_properties", action="store_true", help="upload device properties"
        )

        self.add_argument("--summary", action="store_true", help="print scan summary")

        self.add_argument(
            "--print_network", action="store_true", help="scan ipv4 network for devices"
        )

        self.add_argument(
            "--upload_network",
            action="store_true",
            help="send ipv4 network devices to db",
        )

        self.add_argument(
            "--print_host_ports",
            action="store_true",
            help="print open ports on network hosts",
        )

        self.add_argument(
            "--upload_host_ports",
            action="store_true",
            help="upload open ports on network hosts to db",
        )
        self.add_argument(
            "--ignore_non_whois",
            action="store_true",
            help="ignore iam from addresses not in whois_address argument",
        )
        self.add_argument(
            "--foreignbbmd",
            help="IP for BBMD to use"
        )
        self.add_argument(
            "--foreignttl",
            help="TTL for foreign Device Registration",
            default=60
        )


@bacpypes_debugging
class AutoScan(BIPForeignApplication):
    def __init__(self, *args, **kwargs):
        self._debug = _debug
        self.timeout = int(kwargs.get("timeout", 60))
        self.building_name = kwargs.get("building_name", None)
        self.client_name = kwargs.get("client_name", None)
        self.args = None

        self.device_addresses = []
        self._request = None
        self.first_step = True
        if "foreignbbmd" in kwargs:
            print("initializing BIPForeign")
            BIPForeignApplication.__init__(self, args[0], args[1], kwargs["foreignbbmd"], kwargs["foreignttl"])
        else:
            BIPSimpleApplication.__init__(self, *args)
        # Queue allow this to be thrown to a background thread or process
        self.queue = Queue()
        self.portscan_queue = Queue()
        self.default_props = (
            "units",
            "objectName",
            "description",
            "presentValue",
            "stateText",
        )
        self.device_properties = NetworkProperties()
        self.uploaded_devices = set()
        self.process_steps = []
        self.completed_steps = []
        self.after_io_steps = []
        self.step_in_process = None
        self.found_devices_processor = RecurringFunctionTask(
            5000, AutoScan.process_found_devices, self
        )
        self.found_devices_processor.install_task()
        self.requests_out = 0
        self.total_requests_out = 0
        self.last_requests_out = 0
        self.requests_out_same_count = 0
        self.requests_error_count = 0
        self.request_errors = []
        self.host_ports = (
            20,
            21,
            22,
            23,
            25,
            80,
            111,
            135,
            137,
            138,
            139,
            443,
            445,
            548,
            631,
            993,
            995,
            49152,
            62078,
            47808,
            47809,
            8443,
            8080,
            8888,
            8088,
        )
        self.unique_devices = None
        self.device_index = None
        self.whois_address = None
        self.ignore_non_whois = False
        self.ignore_iam = False

    def final_task(self):
        try:
            print(len(self.process_steps))
            if len(self.process_steps):
                if self.step_in_process:
                    self.completed_steps.append(self.step_in_process)
                step = self.process_steps.pop(0)
                print(step)
                if self.first_step:
                    OneShotDelayFunction(5, getattr(AutoScan, step), self)
                    self.first_step = False
                else:
                    OneShotDelayFunction(0, getattr(AutoScan, step), self)

                AutoScan._debug("processing step: {} in final_task".format(step))
                self.step_in_process = step

            else:
                stop()

        except Exception as e:
            print(f"Exception in final_task: {e}")
            traceback.print_exc()

    def kill_device_processor(self):
        self.found_devices_processor.suspend_task()
        # Not sure this is a good way to do this, but once we timeout, we don't
        # care about incoming IAmRequests
        # self.do_IAmRequest = None
        self.ignore_iam = True
        OneShotDelayFunction(1, AutoScan.final_task, self)

    def install_matched_devices(self):
        # new_devices = self.match_devices()
        # self.device_configs = self.get_device_configs(new_devices)
        # self.registry_configs = self.get_registry_configs(new_devices)
        # self.install_devices()
        for device, registry in self.registry_configs.items():
            self.install_registry_config(registry)
        for device, config in self.device_configs.items():
            self.install_device_config(config)
        self.task_complete()

    def task_complete(self, timeout=1):
        print("task complete")
        print(self.process_steps)
        OneShotDelayFunction(timeout, AutoScan.final_task, self)

    def install_device_config(self, config):
        with open("temp.device", "w") as tempfile:
            tempfile.write(json.dumps(config))

        subprocess.call(
            "/var/lib/volttron/env/bin/vctl config store platform.driver "
            "devices/{}/{}/{} temp.device".format(
                self.client_name,
                self.building_name,
                config["driver_config"]["device_name"],
            ),
            shell=True,
        )
        os.remove("temp.device")

    def install_registry_config(self, config):
        with open("temp.registry", "w") as tempfile:
            tempfile.write(json.dumps(config))
        subprocess.call(
            "/var/lib/volttron/env/bin/vctl config store platform.driver "
            "registry_configs/{} temp.registry".format(config[0]["Device ID"]),
            shell=True,
        )
        os.remove("temp.registry")

    def add_step(self, step):
        if (
            hasattr(self, step)
            and callable(getattr(self, step, None))
            and step not in self.process_steps
        ):
            print(step)
            self.process_steps.append(step)

    def get_queue(self):
        return self.queue

    def show_dead_devices(self):
        try:
            dead_devices = {
                device: topics
                for device, topics in self.devices.items()
                if int(device) not in [id for id, address in self.device_addresses]
            }
            report_devices = {
                device: topics[0]["Volttron Point Name"].split(">")[0]
                for device, topics in dead_devices.items()
            }
            print(json.dumps(report_devices, indent=4, sort_keys=True))
            print(
                "There are {} devices in this registry not responding to"
                " whois requests".format(len(dead_devices))
            )
        except Exception as e:
            if _debug:
                AutoScan._debug(
                    "Exception in final_task: {}, {}".format(e, traceback.print_exc())
                )
        finally:
            OneShotDelayFunction(1, AutoScan.final_task, self)

    def wait_for_io(self):
        if not getattr(self, "waiting_for_io", None):
            print("Waiting for IO")
            self.waiting_for_io = True
            self.wait_for_io_step()

    def wait_for_io_step(self):
        if self.requests_out - self.requests_error_count < 1:
            print("Requests made == to error count + responses")
            self.requests_out = 0
            self.requests_error_count = 0
            self.total_requests_out = 0
            self.waiting_for_io = None
            if len(self.after_io_steps) > 0:
                for step in self.after_io_steps:
                    self.process_steps.insert(0, step)
                self.after_io_steps = []
            self.task_complete()
        else:
            if self.requests_out == self.last_requests_out:
                self.requests_out_same_count += 1
                if self.requests_out_same_count > 49:
                    print(
                        "finishing task, {} requests timed out".format(
                            self.requests_out
                        )
                    )
                    self.requests_out = 0
            else:
                self.requests_out_same_count = 0

            print(
                "Waiting for IO to complete, {} remaining"
                " requests, {} errors, total request: {}".format(
                    self.requests_out,
                    self.requests_error_count,
                    self.total_requests_out,
                )
            )
            OneShotDelayFunction(
                max(self.requests_out // 1000, 5), AutoScan.wait_for_io_step, self
            )
            self.last_requests_out = self.requests_out

    def do_IAmRequest(self, apdu):
        if self.ignore_iam:
            return
        print("in IAM Request")
        sys.stdout.flush()
        # check for required parameters
        if apdu.iAmDeviceIdentifier is None:
            raise MissingRequiredParameter("iAmDeviceIdentifier required")
        if apdu.maxAPDULengthAccepted is None:
            raise MissingRequiredParameter("maxAPDULengthAccepted required")
        if apdu.segmentationSupported is None:
            raise MissingRequiredParameter("segmentationSupported required")
        if apdu.vendorID is None:
            raise MissingRequiredParameter("vendorID required")

        # extract the device instance number
        device_instance = apdu.iAmDeviceIdentifier[1]

        # extract the source address
        device_address = apdu.pduSource
        if (
            self.ignore_non_whois
            and self.whois_address
            and device_address != Address(self.whois_address)
        ):
            return
        if self.ignore_non_whois and (
            device_instance > self.high_limit or device_instance < self.low_limit
        ):
            return

        sys.stdout.write("getting apdus? " + str(device_address) + "\n")
        sys.stdout.flush()
        self.queue.put_nowait((device_instance, str(device_address)))
        # BIPForeignApplication.do_IamRequest(self, apdu)

    def load_visual_bacnet_devices(self, device_file):
        devices = defaultdict(list)
        with open(device_file, encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                # print(row)
                if row["IP Address"] != "":
                    current_address = row["IP Address"]
                elif row["BACnet Network"] != "" and row["BACnet Address"] != "":
                    current_address = f'{row["BACnet Network"]}:{row["BACnet Address"]}'
                else:
                    continue
                self.queue.put_nowait((row["BACnet ID"], current_address))
                self.process_found_devices()

    def load_csv_devices(self, device_file):
        devices = defaultdict(list)
        with open(device_file, encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                devices[row[0]] = list()
        self.devices = devices
        print(self.devices)

    def load_devices(self, topic_file, id_field="Device ID"):
        devices = defaultdict(list)
        with open(topic_file) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                devices[row[id_field]].append(row)
        self.devices = devices

    def scan_devices(self):
        print("in scan devices")
        self.ignore_iam = False
        if not getattr(self, "devices", None):
            print("you must provide a topics list to scan for device" " addresses")
            stop()
        self.this_scanner = self.device_list_scanner()
        self.scannerTask = RecurringFunctionTask(500, AutoScan.scan_device, self)
        self.scannerTask.install_task()

    def alive_hosts(self, responses):
        alive_hosts = []
        for host, response in responses.items():
            if "100% packet loss" not in response:
                alive_hosts.append(host)
        self.alive_hosts = alive_hosts

    # def scan_network(self):
    #     self.host_responses = {}
    #     self.host_processes = {}
    #     if_add = ni.ifaddresses('enp3s0')[2][0]
    #     ip = ipaddress.ip_interface(if_add['addr'] + '/' + if_add['netmask'])
    #     for host in ip.network.hosts():
    #         self.host_processes[host] = subprocess.Popen(
    #             ['ping', '-n', '-c 1', '-W 1', str(host)],
    #             stdout=subprocess.PIPE)
    #     while len(self.host_processes) > 0:
    #         for host in tuple(self.host_processes.keys()):
    #             if self.host_processes[host].poll() is not None:
    #                 process = self.host_processes.pop(host)
    #                 self.host_responses[host] = process.communicate(
    #                 )[0].decode('UTF-8')
    #         time.sleep(1)
    #     self.alive_hosts(self.host_responses)
    #     self.task_complete()

    def scan_host_ports(self, host):
        port_results = {}
        for port in self.host_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((str(host), port))
            sock.close()
            if result == 0:
                port_results[port] = True
            else:
                port_results[port] = False
                self.portscan_queue.put_nowait({str(host): port_results})

    def scan_alive_host_ports(self):
        self.portscan_threads = []
        for host in self.alive_hosts:
            hostscanner = threading.Thread(target=self.scan_host_ports, args=(host))
            hostscanner.start()
            self.portscan_threads.append(hostscanner)
            while True:
                threads_done = True
                for thread in self.portscan_threads:
                    if thread.is_alive():
                        threads_done = False
            if threads_done:
                break
            while not self.portscan_queue.empty():
                for host, ports in self.portscan_queue.get_nowait():
                    self.portscan_results[host] = ports
            time.sleep(1)
        self.portscan_threads = None
        self.task_complete()

    def print_host_ports(self):
        print(self.portscan_results)
        self.task_complete()

    def print_network(self):
        print(self.alive_hosts)
        self.task_complete()

    def scan_bacnet(self):
        self.ignore_iam = False
        # self.do_IAmRequest = self.not_do_IAmRequest
        if self.low_limit and self.high_limit:
            print(
                "starting scan with limits: {}-{}".format(
                    self.low_limit, self.high_limit
                )
            )
            self.who_is(low_limit=self.low_limit, high_limit=self.high_limit)
        elif self.whois_address:
            print("sending whois to {}".format(self.whois_address))
            try:
                print(f"running do_whois_address for address={self.whois_address}")
                self.who_is(address=Address(self.whois_address))
            except Exception as e:
                print(f"exception: {e}")
                self.task_complete(timeout=self.timeout)
                return
        else:
            self.who_is()
        self.task_complete(timeout=self.timeout)

    def scan_device(self):
        try:
            device = next(self.this_scanner)
            if _debug:
                AutoScan._debug("Device Scan Initiated: {}".format(str(device)))
        except StopIteration:
            if _debug:
                AutoScan._debug("Device Whois complete")
            OneShotDelayFunction(self.timeout, AutoScan.final_task, self)
            self.scannerTask.suspend()

    def device_list_scanner(self):
        scan_list = [int(key) for key in self.devices.keys()]
        print(scan_list)
        for device in scan_list:
            self.who_is(low_limit=device, high_limit=device)
            yield device

    def match_devices(self):
        device_ids = self.devices.keys()
        new_devices = {}
        for device_id, device_address in self.device_addresses:
            if str(device_id) in device_ids:
                topic_list = self.devices[str(device_id)]
                new_topic_list = []
                for topic in topic_list:
                    topic["BACnet Address"] = device_address
                    new_topic_list.append(topic)
                device_name = new_topic_list[0]["Volttron Point Name"].split(">")[0]
                new_devices[device_id] = {
                    "topics": new_topic_list,
                    "device_name": device_name,
                }
        return new_devices

    def get_device_configs(self, devices):
        device_configs = {}
        for device, props in devices.items():
            topics = props["topics"]
            device_config = {
                "driver_type": "bacnet",
                "registry_config": "config://registry_configs/" + str(device),
                "interval": "900",
                "driver_config": {
                    "device_address": topics[0]["BACnet Address"],
                    "device_id": device,
                    "device_name": props["device_name"],
                },
            }
            device_configs[device] = device_config
        return device_configs

    def get_registry_configs(self, devices):
        registry_configs = {}
        for device, props in devices.items():
            registry_configs[device] = props["topics"]
        return registry_configs

    def get_new_configs(self):
        try:
            jwt = os.environ.get("ACE_JWT", "")
            print("getting configs")
            assert self.building_name is not None
            url = f"https://manager.aceiot.cloud/api/sites/{self.building_name}/configured_points"
            page = 1
            self.device_configs = {}
            self.registry_configs = {}
            device_points = {}
            lcds = {}
            points_list = []
            while True:
                response = requests.get(
                    url,
                    params={"page": page, "per_page": 500},
                    headers={"authorization": f"Bearer {jwt}"},
                )
                print(response.status_code)
                points = response.json()["items"]
                if points is None:
                    print("error: response with points list is empty")
                    return
                points_list = points_list + points
                page += 1
                if len(points) < 500:
                    print(f"API calls complete, got {len(points_list)} points")
                    break
            for point in points_list:
                device_string = f"{point['bacnet_data']['device_address']}-{point['bacnet_data']['device_id']}"
                device_id = point["bacnet_data"]["device_id"]
                collect_interval = point["collect_interval"]
                last = lcds.get(device_id, collect_interval)
                try:
                    lcds[device_id] = min(last, collect_interval)
                except TypeError:
                    print(f"WARNING: no collect interval for {device_id}")
                    continue
                if device_id not in device_points:
                    device_points[device_id] = point

            for device_string, point in device_points.items():
                bacnet_data = point["bacnet_data"]
                device_id = bacnet_data["device_id"]
                device_config = {
                    "driver_type": "bacnet",
                    "registry_config": f"config://registry_configs/{bacnet_data['device_address']}-{device_id}",
                    "interval": lcds[device_id],
                    "driver_config": {
                        "device_address": bacnet_data["device_address"],
                        "device_id": device_id,
                        "device_name": bacnet_data["device_name"],
                        "use_read_multiple": bacnet_data.get("use_read_multiple", True),
                        "timeout": bacnet_data.get("timeout", "30"),
                        "proxy_address": bacnet_data.get(
                            "bacnet_proxy", "platform.bacnet_proxy"
                        ),
                    },
                }
                self.device_configs[device_id] = device_config

            for point in points_list:
                if not point.get("collect_interval"):
                    continue
                bacnet_data = point["bacnet_data"]
                device_id = bacnet_data["device_id"]
                device_string = f"{bacnet_data['device_address']}-{device_id}"
                registry_config = {
                    "Index": bacnet_data["object_index"],
                    "Unit Details": "",
                    "BACnet Object Type": bacnet_data["object_type"],
                    "BACnet Address": bacnet_data["device_address"],
                    "Writable": str(bacnet_data.get("writable", "False")),
                    "Units": bacnet_data.get("units", ""),
                    "Volttron Point Name": "/".join(point["name"].split("/")[-2:]),
                    "Write Priority": bacnet_data.get("write_priority", ""),
                    "Device ID": device_id,
                    "Property": "presentValue",
                    "Reference Point Name": "{}/{}/{}".format(
                        device_id,
                        bacnet_data["object_type"],
                        bacnet_data["object_index"],
                    ),
                    "Global Topic ID": point["name"],
                    "Interval Multiplier": str(
                        int(int(point["collect_interval"]) / lcds[device_id])
                    ),
                }
                self.registry_configs[device_string] = self.registry_configs.get(
                    device_string, list()
                )
                self.registry_configs[device_string].append(registry_config)
            total_points = 0
            for dev, config in self.registry_configs.items():
                total_points = total_points + len(config)
                print(f"{dev} has {len(config)} points, total: {total_points}")
            self.install_devices(self.building_name)
        except Exception as error:
            AutoScan._exception("exception: %r", error)
            traceback.print_exc()
            raise Exception

    def retrieve_configs(self):  # , site):
        self.get_new_configs()
        OneShotDelayFunction(1, AutoScan.final_task, self)
        return

    def install_devices(self, site):
        for device, config in self.device_configs.items():
            device_string = f"{config['driver_config']['device_address']}-{config['driver_config']['device_id']}"
            self.install_registry_config_new(self.registry_configs[device_string])
            self.install_device_config_new(config, site)

    def install_device_config_new(self, config, site):
        device_string = f"{config['driver_config']['device_address']}-{config['driver_config']['device_id']}"
        if not config["driver_config"]["device_address"] or not config["driver_config"]["device_id"]:
            print(f"ERROR: {device_string} has no address or id")
            return
        path = "devices/{}/{}/{}".format(
            self.client_name, site, device_string
        )
        print(
            f'Installing device config: {config["driver_config"]["device_address"]} - {config["driver_config"]["device_id"]} to {path}'
        )
        with open("temp.device", "w") as tempfile:
            tempfile.write(json.dumps(config))

        subprocess.call(
            "/var/lib/volttron/env/bin/vctl config store platform.driver " + path + " temp.device",
            shell=True,
        )
        os.remove("temp.device")

    def install_registry_config_new(self, config):
        if not config[0]['BACnet Address'] or not config[0]['Device ID']:
            print(f"ERROR: {config[0]['BACnet Address']}-{config[0]['Device ID']} has no address or id")
            return
        device_string = f"{config[0]['BACnet Address']}-{config[0]['Device ID']}"
        path = f"registry_configs/{device_string}"
        print(f"Installing registry config: - {device_string} to {path}")
        with open("temp.registry", "w") as tempfile:
            tempfile.write(json.dumps(config))

        subprocess.call(
            "/var/lib/volttron/env/bin/vctl config store platform.driver " + path + " temp.registry",
            shell=True,
        )
        os.remove("temp.registry")

    def process_found_devices(self):
        try:
            while not self.queue.empty():
                self.device_addresses.append(self.queue.get_nowait())
                print("adding to device_addresses")
        except Empty:
            pass

    def process_address(self, address):
        if ":" in address:
            network, device = address.split(":")
            try:
                int(network)
                int(device)
                return address
            except:
                pass
            if any([x in device.lower() for x in "abcdef"]):
                if len(device) == 8:
                    return f"{network}:{'.'.join([str(int(x, base=16)) for x in [(device[i:i+2]) for i in range(0, 8, 2)]])}"
                return f"{network}:{int(device, base=16)}"
            else:
                return address
        if self.args.ini.address.split(":") == [self.args.ini.address]:
            split_address = address.split(":")
            if len(split_address) == 2:
                try:
                    ipaddress.ip_address(split_address[1])
                    return split_address[1]
                except ValueError:
                    return address
        return address

    def read_properties_list(self):
        if not self.unique_devices:
            self.unique_devices = list(set(self.device_addresses))
            print("Creating unique device list: {}".format(self.unique_devices))
            print("Found {} devices".format(len(self.unique_devices)))
        if not self.device_index:
            self.device_index = 0
        if self.device_index < len(self.unique_devices):
            id, address = self.unique_devices[self.device_index]
            # print(address)
            dev_addr = self.process_address(address)
            # print(dev_addr)
            if dev_addr:
                print("reading properties for device {} at {}".format(id, dev_addr))
                self.read_properties(dev_addr, id)
                # self.device_properties[address]["device_id"] = id
            self.device_index += 1
            if self.device_index < len(self.unique_devices):
                self.after_io_steps.insert(0, "upload_device_data")
                self.after_io_steps.insert(0, "read_properties_list")
        else:
            # self.after_io_steps.insert(0, 'upload_device_data')
            self.task_complete()
        print(
            f"{self.device_index} scanned of {len(self.unique_devices)} at {datetime.now().isoformat()}"
        )
        # OneShotDelayFunction(
        #     1, AutoScan.final_task, self)

    def read_properties_device(self):
        self.read_properties(self.prop_address, self.prop_id)

    def read_properties(self, addr, device_id):
        if _debug:
            AutoScan._debug(
                "read properties request, addr:{}, id:{}".format(addr, device_id)
            )

        try:
            # kick off requests for the names and object lists
            self.property_request(
                "device", "objectName", device_id, addr, self.device_property_response
            )
            self.wait_for_io()

            if _debug:
                AutoScan._debug(
                    "sent request for device name for device: {}"
                    " at address: {}".format(device_id, addr)
                )

            self.property_request(
                "device",
                "objectList",
                device_id,
                addr,
                self.device_property_response,
                index=0,
            )

            self.wait_for_io()
            if _debug:
                AutoScan._debug(
                    "sent request for object list for device: {}"
                    " at address: {}".format(device_id, addr)
                )

        except Exception as error:
            AutoScan._exception("exception: %r", error)
            traceback.print_exc()
        self.current_device_id = device_id
        self.current_device_addr = addr
        self.wait_for_io()

    def property_request(self, obj_type, prop_id, obj_inst, addr, callback, index=None):
        # build a request
        request = ReadPropertyRequest(
            objectIdentifier=(obj_type, int(obj_inst)),
            propertyIdentifier=prop_id,
            propertyArrayIndex=index,
        )
        request.pduDestination = Address(addr)
        self.send_request(request, callback)

    def send_request(self, request, callback):
        # make an IOCB
        iocb = IOCB(request)
        if _debug:
            AutoScan._debug("\t- iocb: %r", iocb)

        iocb.add_callback(callback)

        # give it to the application
        self.request_io(iocb)
        self.requests_out += 1
        self.total_requests_out += 1

    def make_default_property_list(self):
        prop_list = []
        for prop_name in self.default_props:
            prop = PropertyReference(
                propertyIdentifier=prop_name,
            )
            prop_list.append(prop)
        return prop_list

    def object_count_request(self, obj_count, addr, id):
        for obj_index in range(1, obj_count + 1):
            self.property_request(
                "device",
                "objectList",
                id,
                str(addr),
                self.device_property_response,
                index=obj_index,
            )

    def object_property_request(self, obj_id, addr):
        try:
            # print(obj_id)
            if len(obj_id) != 2:
                obj_id = obj_id[0]
            obj_type, obj_inst = obj_id
            for prop_id in self.default_props:
                if get_datatype(obj_type, prop_id) is not None:
                    request = ReadPropertyRequest(
                        objectIdentifier=obj_id,
                        propertyIdentifier=prop_id,
                    )
                    request.pduDestination = addr
                    self.send_request(request, self.object_property_response)
        except Exception as e:
            print(obj_id)
            print(e)
            traceback.print_exc()
            raise e
        self.wait_for_io()

    def object_property_request_multi(self, obj_id, addr):
        try:
            prop_list = self.make_default_property_list()
            read_spec_list = [
                ReadAccessSpecification(
                    objectIdentifier=obj_id,
                    listOfPropertyReferences=prop_list,
                )
            ]
            request = ReadPropertyMultipleRequest(
                listOfReadAccessSpecs=read_spec_list,
            )
            request.pduDestination = addr
            self.send_request(request, self.object_property_response_multi)
        except Exception as e:
            print(e)
            traceback.print_exc()
            raise e
        self.wait_for_io()

    def save_device_properties_csv(self):
        try:
            insert_data = []
            for device, device_data in self.device_properties.items():
                device_id = device_data.pop("device_id", "")
                device_name = device_data.pop("device_name", "")
                for objecttype, object_list in device_data.items():
                    for objectindex, object_data in object_list.items():
                        try:
                            record = {
                                "description": object_data.get("description", ""),
                                "name": object_data.get("objectName", ""),
                                "objecttype": objecttype,
                                "objectindex": objectindex,
                                "device_id": device_id,
                                "device_addr": device,
                                "units": object_data.get("units", ""),
                                "device_name": device_name,
                                "state_text": object_data.get("stateText", ""),
                                # "site": site_name,
                                "write_priority": None,
                                "present_value": object_data.get("presentValue", ""),
                            }
                            insert_data.append(record)
                        except AttributeError as e:
                            pass
            with open("device_properties.csv", "w+") as prop_file:
                writer = csv.DictWriter(
                    prop_file, fieldnames=sorted(insert_data[0].keys())
                )
                writer.writeheader()
                for prop in insert_data:
                    writer.writerow(prop)
        except Exception as e:
            print(e)
            traceback.print_exc()
            raise e
        print("scheduling final task")
        OneShotDelayFunction(1, AutoScan.final_task, self)

    def print_device_properties(self):
        print(self.device_properties)
        print("scheduling final task")
        OneShotDelayFunction(1, AutoScan.final_task, self)

    def device_property_response(self, iocb):
        value, datatype, apdu = self.property_response(iocb)
        data = apdu.dict_contents()
        print(value)
        try:
            if datatype.__name__ == "ArrayOfObjectIdentifier":
                if apdu.propertyArrayIndex == 0:
                    self.object_count_request(
                        value, apdu.pduSource, apdu.objectIdentifier[1]
                    )
                else:
                    self.object_property_request(value, apdu.pduSource)
            elif data["objectIdentifier"][0] == "device":
                self.device_properties[data["source"]]["device_id"] = data[
                    "objectIdentifier"
                ][1]
                self.device_properties[data["source"]]["device_name"] = value

        except Exception as e:
            print(e)
            traceback.print_exc()
            # self.task_complete()

    def object_property_response_multi(self, iocb):
        value, datatype, apdu = self.property_response_multi(iocb)

    def object_property_response(self, iocb):
        try:
            response = self.property_response(iocb)
            if response is not None:
                value, datatype, apdu = response
                data = apdu.dict_contents()
                (
                    self.device_properties[data["source"]][data["objectIdentifier"][0]][
                        data["objectIdentifier"][1]
                    ][data["propertyIdentifier"]]
                ) = str(value)

        except Exception as e:
            print(e)
            traceback.print_exc()
            raise e

    def check_iocb(self, iocb):
        self.requests_out -= 1
        # do something for error/reject/abort
        if iocb.ioError:
            args = iocb.args[0]
            print(
                "Error in response, '{}' for {} : {}".format(
                    iocb.ioError, args.objectIdentifier, args.propertyIdentifier
                )
            )
            self.requests_error_count += 1
            self.request_errors.append((iocb.ioError, args))
        elif iocb.ioResponse:
            return iocb.ioResponse
        # handle nothing
        elif _debug:
            AutoScan._debug("\t- ioError or ioResponse expected")
            return None

    def property_response_multi(self, iocb):
        try:
            apdu = self.check_iocb(iocb)

            # should be an ack
            if not isinstance(apdu, ReadPropertyMultipleACK):
                if _debug:
                    AutoScan._debug("    - not an ack")
                return

            # loop through the results
            for result in apdu.listOfReadAccessResults:
                # here is the object identifier
                objectIdentifier = result.objectIdentifier
                if _debug:
                    AutoScan._debug("    - objectIdentifier: %r", objectIdentifier)

                # now come the property values per object
                for element in result.listOfResults:
                    # get the property and array index
                    propertyIdentifier = element.propertyIdentifier
                    if _debug:
                        AutoScan._debug(
                            "    - propertyIdentifier: %r", propertyIdentifier
                        )
                    propertyArrayIndex = element.propertyArrayIndex
                    if _debug:
                        AutoScan._debug(
                            "    - propertyArrayIndex: %r", propertyArrayIndex
                        )

                    # here is the read result
                    readResult = element.readResult

                    if propertyArrayIndex is not None:
                        sys.stdout.write("[" + str(propertyArrayIndex) + "]")

                    # check for an error
                    if readResult.propertyAccessError is not None:
                        sys.stdout.write(
                            " ! " + str(readResult.propertyAccessError) + "\n"
                        )

                    else:
                        # here is the value
                        propertyValue = readResult.propertyValue

                        # find the datatype
                        datatype = get_datatype(objectIdentifier[0], propertyIdentifier)
                        if _debug:
                            AutoScan._debug("    - datatype: %r", datatype)
                        if not datatype:
                            raise TypeError("unknown datatype")

                        # special case for array parts, others are
                        # managed by cast_out
                        if issubclass(datatype, Array) and (
                            propertyArrayIndex is not None
                        ):
                            if propertyArrayIndex == 0:
                                value = propertyValue.cast_out(Unsigned)
                            else:
                                value = propertyValue.cast_out(datatype.subtype)
                        else:
                            value = propertyValue.cast_out(datatype)
                        if _debug:
                            AutoScan._debug("    - value: %r", value)

                        sys.stdout.write(" = " + str(value) + "\n")
                    sys.stdout.flush()
        except Exception as e:
            print(e)
            traceback.print_exc()

    def property_response(self, iocb):
        apdu = self.check_iocb(iocb)

        # should be an ack
        if not isinstance(apdu, ReadPropertyACK):
            if _debug:
                AutoScan._debug("\t- not and ack")
            return

        # find the datatype
        datatype = get_datatype(apdu.objectIdentifier[0], apdu.propertyIdentifier)
        if _debug:
            AutoScan._debug("\t- datatype: %r", datatype)
        if not datatype:
            raise TypeError("unknown datatype")
        try:
            if issubclass(datatype, Array) and (apdu.propertyArrayIndex is not None):
                if apdu.propertyArrayIndex == 0:
                    value = apdu.propertyValue.cast_out(Unsigned)
                else:
                    value = apdu.propertyValue.cast_out(datatype.subtype)
            else:
                value = apdu.propertyValue.cast_out(datatype)
        except Exception as e:
            print(e)
            traceback.print_exc()

        if _debug:
            AutoScan._debug("\t- value: %r", value)
        return (value, datatype, apdu)

    def store_devices(self, device_file="devices.csv"):
        try:
            with open(device_file, "w") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(self.device_addresses)
        except IOError as e:
            print("device store fail ", e)

        OneShotDelayFunction(1, AutoScan.final_task, self)

    def retrieve_devices(self, device_file="devices.csv"):
        try:
            with open(device_file, "r") as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    self.device_addresses.append(row)
        except Exception as e:
            print(e)
            print("device retrieve fail")

        OneShotDelayFunction(1, AutoScan.final_task, self)

    def print_devices(self):
        for id, address in self.device_addresses:
            print("device_id: {}\tdevice_address: {}".format(id, address))
        self.task_complete()

    def get_new_upload_format(self):
        new_data = []
        for device_addr, dev_data in self.device_properties.items():
            device_name = dev_data.get("device_name", "")
            device_id = dev_data["device_id"]
            device_description = dev_data.get("description", "")
            if device_addr in self.uploaded_devices:
                continue
            for object_type, bacnet_objects in dev_data.items():
                # print(object_type)
                # print(bacnet_objects)
                if isinstance(bacnet_objects, dict):
                    if len(bacnet_objects) > 0:
                        self.uploaded_devices.add(device_addr)
                    for object_index, bacnet_object in bacnet_objects.items():
                        new_data.append(
                            {
                                "name": "{}/{}/{}-{}/{}/{}".format(
                                    self.client_name,
                                    self.building_name,
                                    device_addr,
                                    device_id,
                                    object_type,
                                    object_index,
                                ),
                                "site": self.building_name,
                                "client": self.client_name,
                                "bacnet_data": {
                                    "device_address": device_addr,
                                    "device_id": int(device_id),
                                    "object_type": object_type,
                                    "object_index": object_index,
                                    "object_name": bacnet_object.get("objectName", ""),
                                    "object_units": bacnet_object.get("units", ""),
                                    "device_name": device_name,
                                    "device_description": device_description,
                                    "object_description": bacnet_object.get(
                                        "description", ""
                                    ),
                                    "scrape_interval": 0,
                                    "scrape_enabled": False,
                                    "present_value": bacnet_object.get(
                                        "presentValue", ""
                                    ),
                                },
                            }
                        )
        print(f"{len(self.uploaded_devices)} devices uploaded so far")
        return {"points": new_data}

    def upload_device_data(self):
        new_upload = True
        old_upload = False
        jwt = os.environ.get("ACE_JWT", "")
        upload_url = (
            "http://10.1.4.70:8000/"
            + "machine/sites/"
            + self.building_name
            + "/"
            + self.client_name
            + "/bacnet_points"
        )
        new_upload_url = "https://manager.aceiot.cloud/api/points/"
        try:
            if self.building_name:
                if _debug:
                    AutoScan._debug(self.device_properties)
                print("making it to request")
                with open("test_output.json", "w") as f:
                    json.dump(self.device_properties, f)
                if new_upload:
                    data = self.get_new_upload_format()
                    print("data is loading")
                    for i in range(0, len(data["points"]), 4000):
                        new_upload_chunk = {"points": data["points"][i : i + 4000]}
                        new_result = requests.post(
                            new_upload_url,
                            json=new_upload_chunk,
                            headers={"authorization": "Bearer {}".format(jwt)},
                        )
                        print(new_result.status_code)
                        print(new_result.text)
                if old_upload:
                    old_result = requests.post(upload_url, json=self.device_properties)
                    print(old_result.status_code)
                    print(old_result.text)
                if self.device_index < len(self.unique_devices):
                    self.process_steps.insert(0, "read_properties_list")
                self.task_complete()
            else:
                print("Error: No building name")
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            traceback.print_tb(exc_traceback)
            print(e)
            self.task_complete()

    def print_summary(self):
        print("Summary:")
        print("Device Count: {}".format(len(self.device_properties)))
        # pprint.pprint(self.device_properties)

        totals = {}
        for device, obj_types in self.device_properties.items():
            print("{}:".format(device))
            for obj_type, objs in obj_types.items():
                print("{}: {}".format(obj_type, len(obj_type)))
                if obj_type not in totals:
                    totals[obj_type] = 0
                totals[obj_type] += len(obj_type)

        print("Totals")
        for obj_type, count in totals.items():
            print("{}: {}".format(obj_type, count))

        self.task_complete()

    def process_args(self, args):
        self.args = args
        if args.ewebcsv:
            deviceScanner.load_devices(args.ewebcsv)
        if args.visualbacnetcsv:
            deviceScanner.load_visual_bacnet_devices(args.visualbacnetcsv)
            deviceScanner.add_step("read_properties_list")
        if args.devicecsv:
            deviceScanner.load_csv_devices(args.devicecsv)
            deviceScanner.add_step("scan_devices")
        if args.retrieve_configs:
            #    deviceScanner.retrieve_configs(args.retrieve_configs)
            deviceScanner.add_step("retrieve_configs")
        if args.scan_device:
            deviceScanner.devices = {args.scan_device: ""}
            deviceScanner.add_step("scan_devices")
        if args.scan_devices:
            deviceScanner.add_step("scan_devices")
        if args.print_network:
            deviceScanner.add_step("scan_network")
            deviceScanner.add_step("print_network")
        if args.upload_network:
            deviceScanner.add_step("scan_network")
            deviceScanner.add_step("upload_network")
        if args.install_matched:
            deviceScanner.add_step("install_matched_devices")
        if args.show_dead:
            deviceScanner.add_step("show_dead_devices")
        if args.scan_bacnet:
            if args.whois_address:
                deviceScanner.whois_address = args.whois_address
            if args.scan_high_limit and args.scan_low_limit:
                deviceScanner.high_limit = int(args.scan_high_limit)
                deviceScanner.low_limit = int(args.scan_low_limit)
            else:
                deviceScanner.high_limit = None
                deviceScanner.low_limit = None
            deviceScanner.add_step("scan_bacnet")
            deviceScanner.add_step("kill_device_processor")
        if args.store_devices:
            deviceScanner.add_step("store_devices")
        if args.retrieve_devices:
            deviceScanner.add_step("retrieve_devices")
        if args.print_devices:
            deviceScanner.add_step("print_devices")
        if args.readpropsdev and args.readpropsadd:
            deviceScanner.add_step("read_properties_device")
            deviceScanner.prop_address = args.readpropsadd
            deviceScanner.prop_id = args.readpropsdev
        if args.print_properties:
            if not (args.readpropsdev and args.readpropsadd):
                deviceScanner.add_step("read_properties_list")
            deviceScanner.add_step("print_device_properties")
        if args.save_properties_csv:
            if not (args.readpropsdev and args.readpropsadd):
                deviceScanner.add_step("read_properties_list")
            deviceScanner.add_step("save_device_properties_csv")
        if args.upload_properties:
            if not (args.readpropsdev and args.readpropsadd):
                deviceScanner.add_step("read_properties_list")
            deviceScanner.add_step("upload_device_data")
        if args.summary:
            if not (args.readpropsdev and args.readpropsadd):
                deviceScanner.add_step("read_properties_list")
            deviceScanner.add_step("print_summary")
        if args.print_host_ports:
            deviceScanner.add_step("scan_network")
            deviceScanner.add_step("print_network")
        if args.print_host_ports:
            deviceScanner.add_step("scan_network")
            deviceScanner.add_step("scan_alive_host_ports")
            deviceScanner.add_step("print_host_ports")
        if args.ignore_non_whois:
            deviceScanner.ignore_non_whois = True



if __name__ == "__main__":
    args = ScanConfigParser(description=__doc__).parse_args()
    this_device = LocalDeviceObject(
        objectName=args.ini.objectname,
        objectIdentifier=int(args.ini.objectidentifier),
        maxApduLengthAccepted=int(args.ini.maxapdulengthaccepted),
        segmentationSupported=args.ini.segmentationsupported,
        vendorIdentifier=int(args.ini.vendoridentifier),
    )

    client_name = getattr(args, "client_name", None)
    building_name = getattr(args, "building_name", None)
    foreignbbmd = getattr(args, "foreignbbmd", None)
    

    deviceScanner = AutoScan(
        this_device,
        args.ini.address,
        timeout=args.timeout,
        client_name=client_name,
        building_name=building_name,
        foreignbbmd=foreignbbmd,
        foreignttl=int(args.foreignttl)
    )

    deviceScanner.process_args(args)
    deviceScanner.final_task()
    enable_sleeping()
    print("making it to run")
    run()

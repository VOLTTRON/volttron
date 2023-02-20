from __future__ import annotations

import logging
import math
import sys
import time
from argparse import ArgumentParser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, List

import gevent
import pandas as pd
import pvlib
import yaml

from volttron.platform.vip.agent.utils import build_agent

# from typing import List, Optional, Dict
# from threading import Thread
# from threading import Timer

# from ieee_2030_5.utils import serialize_dataclass

# @dataclass
# class ZmqCredentials:
#     address: str
#     publickey: str
#     secretkey: str
#     serverkey: str = None


@dataclass
class AllPoints:
    points: Dict = field(default_factory=dict)
    meta: Dict = field(default_factory=dict)

    def add(self, name: str, value: Any, meta: Dict = {}):
        self.points[name] = value
        self.meta[name] = meta

    def forbus(self) -> List:
        return [self.points, self.meta]

    @staticmethod
    def frombus(message: List) -> AllPoints:
        assert len(message) == 2, "Message must have a length of 2"

        points = AllPoints()

        for k, v in message[0].items():
            points.add(name=k, value=v, meta=message[1].get(k))

        return points


def run_inverter(timesteps=50) -> Generator:
    # PV module
    sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
    module = sandia_modules['Canadian_Solar_CS5P_220M___2009_']
    # Inverter model
    sapm_inverters = pvlib.pvsystem.retrieve_sam('cecinverter')
    inverter = sapm_inverters['ABB__MICRO_0_25_I_OUTD_US_208__208V_']
    irradiance = [900, 1000, 925]
    temperature = [25, 28, 20]
    # Assumed constant power factor
    PF = 0.99
    # Assumed constant AC voltage
    v_ac = 120
    latitude = 32
    longitude = -111.0

    weather_path = Path("~/weather.txt").expanduser()
    if weather_path.exists():
        header = [
            "time(UTC)", "temp_air", "relative_humidity", "ghi", "dni", "dhi",
            "IR(h)", "wind_speed", "wind_direction", "pressure"
        ]
        weather = pd.read_csv(weather_path)
    else:
        weather = pvlib.iotools.get_pvgis_tmy(latitude,
                                              longitude,
                                              map_variables=True)[0]
        result = weather.to_csv(weather_path, header=True)
        print(f"The result is: {result}")

    total_solar_radiance = weather['ghi']
    # assumed that the total solar radiance is equal to ghi(global horizontal irradiance)
    outdoor_temp = weather["temp_air"]
    # both the total_solar_radiace and outdoor_temp has 1hr sampling rate.
    # you should be able modify the sampling rate by resampling it
    for x, y in zip(total_solar_radiance, outdoor_temp):
        dc = pvlib.pvsystem.sapm(x, y, module)
        p_ac = pvlib.inverter.sandia(dc['v_mp'], dc['p_mp'], inverter)
        s_ac = p_ac / PF
        q_ac = math.sqrt(p_ac**2 + s_ac**2)
        i_ac = (s_ac / v_ac) * 1000
        print(
            f"p_ac = {p_ac}, s_ac = {s_ac}, q_ac= {q_ac}, PF = {PF}, v_ac = {v_ac}, i_ac = {i_ac}"
        )
        yield dict(v_mp=dc['v_mp'],
                   p_mp=dc['p_mp'],
                   i_x=dc['i_x'],
                   i_xx=dc['i_xx'],
                   v_oc=dc['v_oc'],
                   i_sc=dc['i_sc'],
                   p_ac=p_ac,
                   s_ac=p_ac,
                   q_ac=q_ac,
                   v_ac=v_ac,
                   i_ac=i_ac,
                   PF=PF)
        # single phase circuit calculation


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    # Impersonate the platform driver which is going to publish all messages
    # to the bus.
    agent = build_agent(identity='platform.driver')
    gen = run_inverter(5)

    topic_to_publish = "devices/inverter1/all"

    for inv in gen:
        points = AllPoints()

        for k, v in inv.items():
            points.add(k, v)
        # publish
        agent.vip.pubsub.publish(peer="pubsub",
                                 topic=f"{topic_to_publish}",
                                 message=points.forbus())
        gevent.sleep(10)

    sys.exit()

    while True:

        print(agent.core.connected)
        gevent.sleep(5)

    parser = ArgumentParser()

    parser.add_argument("agent_config", help="Agent configuration file.")

    opts = parser.parse_args()

    cfg = Path(opts.agent_config)

    if not cfg.is_file():
        print(f"Config file is not valid: {cfg}")
        sys.exit(1)

    yaml.safe_load()

    parser.add_argument(
        "--tls-repo",
        help="TLS repository directory to use, defaults to ~/tls",
        default="~/tls")
    parser.add_argument("--server-host",
                        help="Reference to the utilities server for data.")
    parser.add_argument("--server-port",
                        type=int,
                        default=443,
                        help="Port the server is listening on, default to 443")
    parser.add_argument("--device-id",
                        help="The id of the device for this inverter")
    parser.add_argument(
        "--pin",
        type=int,
        help=
        "PIN for the client to validate that it is connecting to the correct server."
    )

    opts = parser.parse_args()

    path = Path(__file__).parent.parent.parent.joinpath("openssl.cnf")
    repo_dir = Path(opts.tls_repo).expanduser().resolve(strict=True)
    if not repo_dir.exists():
        raise ValueError(f"Invalid repo directory {str(repo_dir)}")
    tls_repo = TLSRepository(repo_dir=repo_dir,
                             openssl_cnffile_template=path,
                             serverhost="gridappsd_dev_2004",
                             clear=False)

    if opts.device_id not in tls_repo.client_list:
        raise ValueError(
            f"device_id: ({opts.device_id}) not in tls repository")

    # print(new_tls_repository.client_list)
    for p in tls_repo.client_list:
        if p == opts.device_id:
            IEEE2030_5_Client(
                cafile=tls_repo.ca_cert_file,
                keyfile=tls_repo.__get_key_file__(opts.device_id),
                certfile=tls_repo.__get_cert_file__(opts.device_id),
                hostname=p,
                server_hostname=opts.server_host,
                server_ssl_port=opts.server_port)

    # Start up a client from the available in the config file.
    client = list(IEEE2030_5_Client.clients)[0]
    for i in range(5):
        # Device capability provides links to the other resources of interest.
        dcap = client.device_capability()
        time.sleep(2)
    # Time request for offsets to keep things closely aligned.
    tm = client.time()
    # The device that this class is available for.
    device = client.end_device()
    # print("EndDevice")
    # print(serialize_dataclass(device))
    #

    # # Registration to test if we have the correct pin for the client to be sure
    # # that it is talking to the correct server
    # reg = client.registration(device)
    # assert reg.pIN == opts.pin
    #
    # curve_list: DERCurveList = client.__get_request__("/curves")
    # curve1 = client.__get_request__(curve_list.DERCurve[0].href)
    #
    # global_programs: DERProgramList = client.__get_request__("/programs")
    # program = client.__get_request__(global_programs.DERProgram[0].href)
    #
    #
    #
    # der_programs = client.der_program_list(device)
    #
    # der_programs = client.der_program_list()

    #print(fsa)
    # edevs = client.end_devices()
    #
    # my_device = client.end_device()
    # self_device = client.self_device()
    # assert my_device == self_device
    # end_devices = client.end_devices()
    # end_device = client.end_device(0)
    # registration = client.registration(end_device)
    #
    # # edev_config = client.request(end_device.ConfigurationLink.href)
    # client.timelink()
    #
    # assert registration.pIN == opts.pin
    #
    # der_list = client.__get_request__(end_device.DERListLink.href)
    # # uuidstr = client.new_uuid()
    # mup = client.mirror_usage_point_list()
    #
    # mup_uuid = client.new_uuid().encode('utf-8')
    # mup_gas_mirroring = MirrorUsagePoint(
    #     mRID=mup_uuid,
    #     description="Gas Mirroring",
    #     roleFlags=bytes(13),
    #     serviceCategoryKind=1,
    #     status=1,
    #     deviceLFDI=end_device.lFDI,
    #     MirrorMeterReading=[MirrorMeterReading(
    #         mRID=mup_uuid,
    #         Reading=Reading(
    #             value=125
    #         ),
    #         ReadingType=ReadingType(
    #             accumulationBehaviour=9,
    #             commodity=7,
    #             dataQualifier=0,
    #             flowDirection=1,
    #             powerOfTenMultiplier=3,
    #             uom=119
    #         )
    #     )]
    # )
    #
    # status, location = client.create_mirror_usage_point(mup_gas_mirroring)
    #
    # point_list = client.mirror_usage_point_list()
    #
    # print(point_list)

    # print(client.new_uuid())
    # print(client.usage_point_list())
    # gen = run_inverter(client)
    # for output in gen:
    #     print(output)

    # threads: List[Thread] = []
    #
    # for index, client in enumerate(IEEE2030_5_Client.clients):
    #     th = Thread(target=run_inverter, args=(client,))
    #     threads.append(th)
    #     th.daemon = True
    #     th.start()
    #
    # while True:
    #     alive = False
    #     for t in threads:
    #         if t.is_alive():
    #             alive = True
    #             break
    #     if alive:
    #         break
    #     time.sleep(1)

    # while True:
    #     try:
    #         time.sleep(0.1)
    #     except KeyboardInterrupt:
    #         sys.stderr.write("Exiting program\n")
    #         sys.exit(0)

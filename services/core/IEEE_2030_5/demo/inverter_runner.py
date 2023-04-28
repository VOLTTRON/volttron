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


class MyInverterAgent(Agent):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._points = {}
        self._points['pf'] = 0.99
        self._generator = None

    @RPC.export
    def set_point(self, point, value):
        self._generator = None
        self._points[point] = value

    @RPC.export
    def get_point(self, point):
        return self._points.get(point)

    @property
    def reset(self):
        return self._generator is not None


def run_inverter(timesteps=50, pf=0.99, latitude=32, longitude=-111.0) -> Generator:
    # PV module
    sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
    module = sandia_modules['Canadian_Solar_CS5P_220M___2009_']
    # Inverter model
    sapm_inverters = pvlib.pvsystem.retrieve_sam('cecinverter')
    inverter = sapm_inverters['ABB__MICRO_0_25_I_OUTD_US_208__208V_']
    irradiance = [900, 1000, 925]
    temperature = [25, 28, 20]
    # Assumed constant power factor
    PF = pf
    print(f"Power Factor: {PF}")
    # Assumed constant AC voltage
    v_ac = 120
    latitude = 32
    longitude = -111.0

    weather_path = Path(__file__).parent.joinpath("weather.txt")
    if weather_path.exists():
        header = [
            "time(UTC)", "temp_air", "relative_humidity", "ghi", "dni", "dhi", "IR(h)",
            "wind_speed", "wind_direction", "pressure"
        ]
        weather = pd.read_csv(weather_path)
    else:
        weather = pvlib.iotools.get_pvgis_tmy(latitude, longitude, map_variables=True)[0]
        result = weather.to_csv(weather_path, header=True)

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
        # print(
        #     f"p_ac = {p_ac}, s_ac = {s_ac}, q_ac= {q_ac}, PF = {PF}, v_ac = {v_ac}, i_ac = {i_ac}"
        # )
        results = dict(PF=PF,
                       p_ac=p_ac,
                       q_ac=q_ac,
                       v_mp=dc['v_mp'],
                       p_mp=dc['p_mp'],
                       i_x=dc['i_x'],
                       i_xx=dc['i_xx'],
                       v_oc=dc['v_oc'],
                       i_sc=dc['i_sc'],
                       s_ac=p_ac,
                       v_ac=v_ac,
                       i_ac=i_ac)
        print(json.dumps(results))
        yield results
        # single phase circuit calculation


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
            "time(UTC)", "temp_air", "relative_humidity", "ghi", "dni", "dhi", "IR(h)",
            "wind_speed", "wind_direction", "pressure"
        ]
        weather = pd.read_csv(weather_path)
    else:
        weather = pvlib.iotools.get_pvgis_tmy(latitude, longitude, map_variables=True)[0]
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
            f"p_ac = {p_ac}, s_ac = {s_ac}, q_ac= {q_ac}, PF = {PF}, v_ac = {v_ac}, i_ac = {i_ac}")
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
    logging.getLogger('volttron.platform.vip.agent.core').setLevel(logging.WARNING)

    from pathlib import Path

    # Impersonate the platform driver which is going to publish all messages
    # to the bus.
    agent = build_agent(identity='platform.driver', agent_class=MyInverterAgent)

    control_path = Path('inverter.ctl')

    while True:

        gen = run_inverter()

        topic_to_publish = "devices/inverter1/all"
        pf = 0.99

        for inv in gen:
            points = AllPoints()

            for k, v in inv.items():
                points.add(k, v)
            # publish
            agent.vip.pubsub.publish(peer="pubsub",
                                     topic=f"{topic_to_publish}",
                                     message=points.forbus())
            gevent.sleep(10)

            if control_path.exists():
                data = control_path.open().read()
                try:
                    obj = json.loads(data)
                except json.decoder.JSONDecodeError:
                    obj = dict(pf=0.99)

                pf = obj.get('pf', 0.99)

    agent.core.stop()
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
from volttron.platform.agent.utils import format_timestamp, get_aware_utc_now
from volttron.platform.vip.agent import Agent
from volttron.platform.vip.agent.subsystems.rpc import RPC
from volttron.platform.vip.agent.utils import build_agent

_log = logging.getLogger(__name__)


class MyInverterAgent(Agent):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._points = {}

    @RPC.export
    def set_point(self, point, value):
        _log.debug(f"Setting {point} to {value}")
        self._points[point] = value

    @RPC.export
    def get_point(self, point):
        return self._points.get(point)

    def get_all_points(self):
        return self._points.keys()

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
        results = dict(
            PF=PF,
            INV_REAL_PWR=p_ac,
            INV_REAC_PWR=q_ac,
        #v_mp=dc['v_mp'],
        #p_mp=dc['p_mp'],
        #i_x=dc['i_x'],
        #i_xx=dc['i_xx'],
        #v_oc=dc['v_oc'],
        #i_sc=dc['i_sc'],
            s_ac=p_ac,
        #v_ac=v_ac,
            BAT_SOC=int(v_ac / p_ac),
        #i_ac=i_ac,
            target_p=p_ac,
            INV_OP_STATUS_MODE=3)
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
        yield dict(INV_REAL_PWR=p_ac,
                   INV_REAC_PWR=q_ac,
                   BAT_SOC=int(v_ac / p_ac),
                   INV_OP_STATUS_MODE=3)
        # v_mp=dc['v_mp'],
        #        p_mp=dc['p_mp'],
        #        i_x=dc['i_x'],
        #        i_xx=dc['i_xx'],
        #        v_oc=dc['v_oc'],
        #        i_sc=dc['i_sc'],
        #        p_ac=p_ac,
        #        s_ac=p_ac,
        #        q_ac=q_ac,
        #        v_ac=v_ac,
        #        i_ac=i_ac,
        #        PF=PF)
        # single phase circuit calculation


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()

    # parser.add_argument("output_file", help="File to write to when data arrives on the bus")
    # opts = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG, force=True)

    logging.getLogger('volttron.platform.vip.agent.core').setLevel(logging.WARNING)
    logging.getLogger('volttron.platform.vip.agent.core').setLevel(logging.WARNING)

    from pathlib import Path

    # Impersonate the platform driver which is going to publish all messages
    # to the bus.
    agent = build_agent(identity='platform.driver', agent_class=MyInverterAgent)

    control_path = Path('inverter.ctl')

    from volttron.platform.messaging import headers as t_header

    while True:

        gen = run_inverter()

        topic_to_publish = "devices/inverter1/all"
        pf = 0.99

        for inv in gen:
            points = AllPoints()

            agent_points = agent.get_all_points()

            for k in agent_points:
                if k in inv:
                    points.add(k, inv[k])
                else:
                    points.add(k, agent.get_point(k))

            # Loop over points adding them to the allpoints dataclass if
            # they are specified.  If they have been set on the agent itself
            # then use that value instead of the one from the generator.
            for k, v in inv.items():
                pt_set = agent.get_point(k)
                if pt_set is not None:
                    points.add(k, pt_set)
                else:
                    points.add(k, v)

            ts = format_timestamp(get_aware_utc_now())
            headers = {t_header.SYNC_TIMESTAMP: ts, t_header.TIMESTAMP: ts}

            _log.info(f"Publishing {points.points}")
            # publish
            agent.vip.pubsub.publish(peer="pubsub",
                                     topic=f"{topic_to_publish}",
                                     headers=headers,
                                     message=points.forbus())
            # with open(Path(opts.output_file), '+a') as fp:
            #     fp.write(json.dumps(dict(headers=headers, message=points.forbus())) + "\n")
            gevent.sleep(10)

    agent.core.stop()

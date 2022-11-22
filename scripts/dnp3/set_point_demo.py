"""
A demo to test dnp3-driver set_point method using rpc call.

Pre-requisite:
- install platform-driver
- configure dnp3-driver
- a dnp3 outstation/server is up and running
- platform-driver is up and running
"""

import random
from volttron.platform.vip.agent.utils import build_agent
from time import sleep
import datetime


def main():
    a = build_agent()
    while True:
        sleep(5)
        print("============")
        try:
            rpc_method = "set_point"
            device_name = "campus-vm/building-vm/Dnp3"

            for i in range(3):
                reg_pt_name = "AnalogOutput_index" + str(i)
                val_to_set = random.random()
                rs = a.vip.rpc.call("platform.driver", rpc_method,
                                    device_name,
                                    reg_pt_name,
                                    val_to_set).get(timeout=10)
                print(datetime.datetime.now(), "point_name: ", reg_pt_name, "response: ", rs)

            # verify
            sleep(1)

            for i in range(3):
                rpc_method = "get_point"
                reg_pt_name = "AnalogOutput_index" + str(i)
                # val_to_set = random.random()
                rs = a.vip.rpc.call("platform.driver", rpc_method,
                                    device_name,
                                    reg_pt_name
                                    ).get(timeout=10)
                print(datetime.datetime.now(), "point_name: ", reg_pt_name, "response: ", rs)
        except Exception as e:
            print(e)


if __name__ == "__main__":
    main()

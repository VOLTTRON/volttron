import logging
import sys
import argparse

from pydnp3 import opendnp3
# from dnp3_python.dnp3station.outstation import MyOutStation

from time import sleep
from volttron.platform.vip.agent.utils import build_agent
from services.core.DNP3OutstationAgent.dnp3_outstation_agent.agent import Dnp3Agent as Dnp3OutstationAgent  # agent
from volttron.platform.vip.agent import Agent

import logging
import sys
import argparse

# from pydnp3 import opendnp3
# from dnp3_python.dnp3station.outstation_new import MyOutStationNew

from time import sleep

# from volttron.client.vip.agent import build_agent
# from dnp3_outstation.agent import Dnp3OutstationAgent
# from volttron.client.vip.agent import Agent

DNP3_AGENT_ID = "dnp3_outstation"

stdout_stream = logging.StreamHandler(sys.stdout)
stdout_stream.setFormatter(logging.Formatter('%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s'))

_log = logging.getLogger(__name__)
# _log = logging.getLogger("control_workflow_demo")
_log.addHandler(stdout_stream)
_log.setLevel(logging.INFO)


def input_prompt(display_str=None) -> str:
    if display_str is None:
        display_str = f"""
======== Your Input Here: ==(DNP3 OutStation Agent)======
"""
    return input(display_str)


def setup_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("-aid", "--agent-identity", action="store", default=DNP3_AGENT_ID, type=str,
                        metavar="<peer-name>",
                        help=f"specify agent identity (parsed as peer-name for rpc call), default '{DNP3_AGENT_ID}'.")

    return parser


def print_menu():
    welcome_str = rf"""
========================= MENU ==================================
<ai> - set analog-input point value
<ao> - set analog-output point value
<bi> - set binary-input point value
<bo> - set binary-output point value

<dd> - display database
<di> - display (outstation) info
<cr> - config then restart outstation
=================================================================
"""
    print(welcome_str)


def check_agent_id_existence(agent_id: str, vip_agent: Agent):
    rs = vip_agent.vip.peerlist.list().get(5)
    if agent_id not in rs:
        raise ValueError(f"There is no agent named `{agent_id}` available on the message bus."
                         f"Available peers are {rs}")
        # _log.warning(f"There is no agent named `{agent_id}` available on the message bus."
        #                  f"Available peers are {rs}")


def main(parser=None, *args, **kwargs):
    if parser is None:
        # Initialize parser
        parser = argparse.ArgumentParser(
            prog="dnp3-outstation",
            description=f"Run a dnp3 outstation agent. Specify agent identity, by default `{DNP3_AGENT_ID}`",
            # epilog="Thanks for using %(prog)s! :)",
        )
        parser = setup_args(parser)

    # Read arguments from command line
    args = parser.parse_args()
    # create volttron vip agent to evoke dnp3-agent rpc calls
    a = build_agent()
    peer = args.agent_identity  # note: default {DNP3_AGENT_ID} or "test-agent"
    # print(f"========= peer {peer}")
    check_agent_id_existence(peer, a)

    def get_db_helper():
        _peer_method = Dnp3OutstationAgent.display_outstation_db.__name__
        _db_print = a.vip.rpc.call(peer, _peer_method).get(timeout=10)
        return _db_print

    def get_config_helper():
        _peer_method = Dnp3OutstationAgent.get_outstation_config.__name__
        _config_print = a.vip.rpc.call(peer, _peer_method).get(timeout=10)
        _config_print.update({"peer": peer})
        return _config_print

    sleep(2)
    # Note: if without sleep(2) there will be a glitch when first send_select_and_operate_command
    #  (i.e., all the values are zero, [(0, 0.0), (1, 0.0), (2, 0.0), (3, 0.0)]))
    #  since it would not update immediately

    count = 0
    while count < 1000:
        # sleep(1)  # Note: hard-coded, master station query every 1 sec.
        count += 1
        # print(f"=========== Count {count}")
        peer_method = Dnp3OutstationAgent.is_outstation_connected
        if a.vip.rpc.call(peer, peer_method.__name__, ).get(timeout=10):
            # print("Communication Config", master_application.get_config())
            print_menu()
        else:
            print_menu()
            print("!!!!!!!!! WARNING: The outstation is NOT connected !!!!!!!!!")
            print(get_config_helper())
        # else:
        #     print("Communication error.")
        #     # print("Communication Config", outstation_application.get_config())
        #     print(get_config_helper())
        #     print("Start retry...")
        #     sleep(2)
        #     continue

        # print_menu()
        option = input_prompt()  # Note: one of ["ai", "ao", "bi", "bo",  "dd", "dc"]
        while True:
            if option == "ai":
                print("You chose <ai> - set analog-input point value")
                print("Type in <float> and <index>. Separate with space, then hit ENTER. e.g., `1.4321, 1`.")
                print("Type 'q', 'quit', 'exit' to main menu.")
                input_str = input_prompt()
                if input_str in ["q", "quit", "exit"]:
                    break
                try:
                    p_val = float(input_str.split(" ")[0])
                    index = int(input_str.split(" ")[1])
                    # outstation_application.apply_update(opendnp3.Analog(value=p_val), index)
                    # result = {"Analog": outstation_application.db_handler.db.get("Analog")}
                    method = Dnp3OutstationAgent.apply_update_analog_input
                    peer_method = method.__name__  # i.e., "apply_update_analog_input"
                    response = a.vip.rpc.call(peer, peer_method, p_val, index).get(timeout=10)
                    result = {"Analog": get_db_helper().get("Analog")}
                    print(result)
                    sleep(2)
                except Exception as e:
                    print(f"your input string '{input_str}'")
                    print(e)
            elif option == "ao":
                print("You chose <ao> - set analog-output point value")
                print("Type in <float> and <index>. Separate with space, then hit ENTER. e.g., `0.1234, 0`.")
                print("Type 'q', 'quit', 'exit' to main menu.")
                input_str = input_prompt()
                if input_str in ["q", "quit", "exit"]:
                    break
                try:
                    p_val = float(input_str.split(" ")[0])
                    index = int(input_str.split(" ")[1])
                    method = Dnp3OutstationAgent.apply_update_analog_output
                    peer_method = method.__name__  # i.e., "apply_update_analog_input"
                    response = a.vip.rpc.call(peer, peer_method, p_val, index).get(timeout=10)
                    result = {"AnalogOutputStatus": get_db_helper().get("AnalogOutputStatus")}
                    print(result)
                    sleep(2)
                except Exception as e:
                    print(f"your input string '{input_str}'")
                    print(e)
            elif option == "bi":
                print("You chose <bi> - set binary-input point value")
                print("Type in <[1/0]> and <index>. Separate with space, then hit ENTER. e.g., `1, 0`.")
                input_str = input_prompt()
                if input_str in ["q", "quit", "exit"]:
                    break
                try:
                    p_val_input = input_str.split(" ")[0]
                    if p_val_input not in ["0", "1"]:
                        raise ValueError("binary-output value only takes '0' or '1'.")
                    else:
                        p_val = True if p_val_input == "1" else False
                    index = int(input_str.split(" ")[1])
                    method = Dnp3OutstationAgent.apply_update_binary_input
                    peer_method = method.__name__
                    response = a.vip.rpc.call(peer, peer_method, p_val, index).get(timeout=10)
                    result = {"Binary": get_db_helper().get("Binary")}
                    print(result)
                    sleep(2)
                except Exception as e:
                    print(f"your input string '{input_str}'")
                    print(e)
            elif option == "bo":
                print("You chose <bo> - set binary-output point value")
                print("Type in <[1/0]> and <index>. Separate with space, then hit ENTER. e.g., `1, 0`.")
                input_str = input_prompt()
                if input_str in ["q", "quit", "exit"]:
                    break
                try:
                    p_val_input = input_str.split(" ")[0]
                    if p_val_input not in ["0", "1"]:
                        raise ValueError("binary-output value only takes '0' or '1'.")
                    else:
                        p_val = True if p_val_input == "1" else False
                    index = int(input_str.split(" ")[1])
                    method = Dnp3OutstationAgent.apply_update_binary_output
                    peer_method = method.__name__
                    response = a.vip.rpc.call(peer, peer_method, p_val, index).get(timeout=10)
                    result = {"BinaryOutputStatus": get_db_helper().get("BinaryOutputStatus")}
                    print(result)
                    sleep(2)
                except Exception as e:
                    print(f"your input string '{input_str}'")
                    print(e)
            elif option == "dd":
                print("You chose <dd> - display database")
                print(get_db_helper())
                sleep(2)
                break
            elif option == "di":
                print("You chose <di> - display (outstation) info")
                print(get_config_helper())
                sleep(3)
                break
            elif option == "cr":
                print("You chose <cr> - config then restart outstation")
                print(f"current self.volttron_config is {get_config_helper()}")
                print(
                    "Type in <port-value-of-int>, then hit ENTER. e.g., `20000`."
                    "(Note: In this script, only support port configuration.)")
                # input_str = input_prompt()
                input_str = input()
                try:
                    # set_volttron_config
                    port_val = int(input_str)
                    method = Dnp3OutstationAgent.update_outstation
                    peer_method = method.__name__
                    response = a.vip.rpc.call(peer, peer_method, port=port_val).get(timeout=10)
                    print("SUCCESS.", get_config_helper())
                    sleep(2)
                except Exception as e:
                    print(f"your input string '{input_str}'")
                    print(e)
                break
            else:
                print(f"ERROR- your input `{option}` is not one of the following.")
                sleep(1)
                break

    _log.debug('Exiting.')
    # outstation_application.shutdown()
    # outstation_application.shutdown()


if __name__ == '__main__':
    main()

import gevent
from volttron.platform.vip.agent import Agent
from volttron.platform import get_address
from volttron.platform.agent.utils import parse_json_config
from volttron.platform.keystore import KeyStore
from argparse import ArgumentParser
from zmq.utils import jsonapi

from pprint import pprint

keystore = KeyStore()
agent = Agent(address=get_address(), identity="master_driver_update_agent",
        publickey=keystore.public(), secretkey=keystore.secret(),
        enable_store=False)

event = gevent.event.Event()
gevent.spawn(agent.core.run, event)
event.wait()

def process_driver_config(config_path, csv_name_map, csv_contents):
    print "Processing config:", config_path
    with open(config_path) as f:
        device_config = parse_json_config(f.read())

    registry_config_file_name = device_config["registry_config"]

    #Sort out name collisions and add to map if needed
    if registry_config_file_name not in csv_name_map:
        print "Processing CSV:", registry_config_file_name
        base_name = registry_config_file_name.split('/')[-1]
        base_name = "registry_configs/" + base_name

        if base_name in csv_contents:
            count = 0
            new_csv_name = base_name + str(count)
            while(new_csv_name in csv_contents):
                count += 1
                new_csv_name = base_name + str(count)

            base_name = new_csv_name


        with open(registry_config_file_name) as f:
            csv_contents[base_name] = f.read()

        csv_name_map[registry_config_file_name] = base_name


    #Overwrite file name with config store reference.
    device_config["registry_config"] = "config://" + csv_name_map[registry_config_file_name]

    new_config_name = "devices"

    for topic_bit in ("campus", "building", "unit", "path"):
        topic_bit = device_config.pop(topic_bit, '')
        if topic_bit:
            new_config_name += "/" + topic_bit

    return new_config_name, device_config


def process_main_config(main_file, keep=False):
    main_config = parse_json_config(main_file.read())
    driver_list = main_config.pop("driver_config_list")
    driver_count = len(driver_list)

    csv_name_map = {}
    csv_contents = {}

    driver_configs = {}

    for config_path in driver_list:
        new_config_name, device_config = process_driver_config(config_path, csv_name_map, csv_contents)

        if new_config_name in driver_configs:
            print "WARNING DUPLICATE DEVICES:", new_config_name, "FOUND IN", config_path

        driver_configs[new_config_name] = device_config

    staggered_start = main_config.pop('staggered_start', None)

    if staggered_start is not None:
        main_config["driver_scrape_interval"] = staggered_start / float(driver_count)

    print "New Main config:"
    pprint(main_config)


    if not keep:
        agent.vip.rpc.call('config.store',
                           'manage_delete_store',
                           'platform.driver').get(timeout=10)

    agent.vip.rpc.call('config.store',
                       'manage_store',
                       'platform.driver',
                       'config',
                       jsonapi.dumps(main_config),
                       config_type="json").get(timeout=10)

    for name, contents in csv_contents.iteritems():
        agent.vip.rpc.call('config.store',
                           'manage_store',
                           'platform.driver',
                           name,
                           contents,
                           config_type="csv").get(timeout=10)

    for name, config in driver_configs.iteritems():
        agent.vip.rpc.call('config.store',
                           'manage_store',
                           'platform.driver',
                           name,
                           jsonapi.dumps(config),
                           config_type="json").get(timeout=10)



if __name__ == "__main__":
    parser = ArgumentParser(description="Update a master configuration to use the configuration store.")

    parser.add_argument('--keep-old', action="store_true",
                        help="Do not remove all files in the master driver's configuration store before adding new configurations.")


    parser.add_argument('main_configuration', type=file,
                        help='Specify the pre-config store main master driver configuration file')

    args = parser.parse_args()
    process_main_config(args.main_configuration, args.keep_old)

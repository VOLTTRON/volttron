import json

import pytest
import os
import shutil
import subprocess
from csv import DictReader
from io import StringIO

from volttrontesting.utils.platformwrapper import create_volttron_home
from volttron.platform.agent.utils import parse_json_config
from volttrontesting.fixtures.volttron_platform_fixtures import build_wrapper, cleanup_wrapper
from volttrontesting.utils.utils import get_rand_vip

METATADATA_FILE_FORMAT = """Metadata file format:
{ "vip-id": [
 { 
     "config-name": "optional. name. defaults to config
     "config": "json config or string config or config file name", 
     "config-type": "optional. type of config - csv or json or raw. defaults to json"
 }, ...
 ],...
}"""


@pytest.fixture(scope="module")
def shared_vhome():
    debug_flag = os.environ.get('DEBUG', False)
    vhome = create_volttron_home()
    yield vhome
    if not debug_flag:
        shutil.rmtree(vhome, ignore_errors=True)


@pytest.fixture()
def vhome():
    debug_flag = os.environ.get('DEBUG', False)
    vhome = create_volttron_home()
    yield vhome
    if not debug_flag:
        shutil.rmtree(vhome, ignore_errors=True)


@pytest.fixture(scope="module")
def single_vinstance():
    address = get_rand_vip()
    wrapper = build_wrapper(address,
                            messagebus='zmq',
                            ssl_auth=False,
                            auth_enabled=False)
    yield wrapper
    cleanup_wrapper(wrapper)


# Only integration test. Rest are unit tests
def test_fail_if_volttron_is_running(single_vinstance, monkeypatch):
    monkeypatch.setenv("VOLTTRON_HOME", single_vinstance.volttron_home)
    process = subprocess.run(["vcfg", "--vhome", single_vinstance.volttron_home,
                              "update-config-store", "--metadata-file", "test"],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )
    assert process.stdout.decode("utf-8").startswith(
        f"VOLTTRON is running using at {single_vinstance.volttron_home}, "
        f"you can add/update single configuration using vctl config command.")
    assert process.returncode == 1


def test_help(monkeypatch, shared_vhome):
    monkeypatch.setenv("VOLTTRON_HOME", shared_vhome)
    process = subprocess.run(["vcfg", "--vhome", shared_vhome, "update-config-store", "--help"],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )
    assert process.stdout.startswith(b"usage: vcfg update-config-store [-h] --metadata-file METADATA_FILE")


def test_no_arg(monkeypatch, shared_vhome):
    monkeypatch.setenv("VOLTTRON_HOME", shared_vhome)
    process = subprocess.run(["vcfg", "--vhome", shared_vhome, "update-config-store"],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )
    assert process.stderr.startswith(b"usage: vcfg update-config-store [-h] --metadata-file METADATA_FILE")


def test_no_args_value(monkeypatch, shared_vhome):
    monkeypatch.setenv("VOLTTRON_HOME", shared_vhome)
    process = subprocess.run(["vcfg", "--vhome", shared_vhome, "update-config-store", "--metadata-file"],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )
    assert process.stderr.startswith(b"usage: vcfg update-config-store [-h] --metadata-file METADATA_FILE")


def test_invalid_file_path(monkeypatch, shared_vhome):
    monkeypatch.setenv("VOLTTRON_HOME", shared_vhome)
    process = subprocess.run(["vcfg", "--vhome", shared_vhome, "update-config-store", "--metadata-file", "invalid"],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )
    expected_message = "Value is neither a file nor a directory: ['invalid']: \n" \
                       "The --metadata-file accepts one or more metadata " \
                       "files or directory containing metadata file\n\n" + METATADATA_FILE_FORMAT

    assert process.stdout.decode('utf-8').strip() == expected_message
    assert process.returncode == 1


@pytest.mark.parametrize('json_metadata, json_file, config_name', [
    ({"vip-id-1": {}}, "no_config_json1", "config"),
    ({"vip-id-1": [{"config-name": "config"}]}, "no_config_json2", "config"),
    ({"vip-id-1": [{"config-name": "new_config", "config_type": "json"}]}, "no_config_json2", "new_config")
])
def test_no_config_metadata(monkeypatch, vhome, json_metadata, json_file, config_name):
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    file_path = os.path.join(vhome, json_file)
    with open(file_path, "w") as f:
        f.write(json.dumps(json_metadata))
    expected_message = f"No config entry found in file {file_path} for vip-id vip-id-1 and " \
                       f"config-name {config_name}\n\n" + METATADATA_FILE_FORMAT
    process = subprocess.run(["vcfg", "--vhome", vhome,
                              "update-config-store", "--metadata-file", file_path],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )

    assert process.stdout.decode('utf-8').strip() == expected_message
    assert process.returncode == 1


def test_invalid_config_class(monkeypatch, vhome):
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    file_path = os.path.join(vhome, "invalid_config_class.json")
    with open(file_path, "w") as f:
        f.write(json.dumps({"vip-id-1": "string config"}))
    expected_message = f"Metadata for vip-identity vip-id-1 in file {file_path} should be a dictionary or " \
                       f"list of dictionary. Got type <class 'str'>\n\n" + METATADATA_FILE_FORMAT
    process = subprocess.run(["vcfg", "--vhome", vhome,
                              "update-config-store", "--metadata-file", file_path],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )

    assert process.stdout.decode('utf-8').strip() == expected_message
    assert process.returncode == 1


def test_incorrect_config_type(monkeypatch, vhome):
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    file_path = os.path.join(vhome, "invalid_config_type.json")
    with open(file_path, "w") as f:
        f.write(json.dumps({"vip-id-1": {"config": "string config for json config-type",
                                         "config-type": "json"}}))
    expected_message = 'Value for key "config" should be one of the following: \n' \
                       '1. filepath \n'\
                       '2. string with "config-type" set to "raw" \n'\
                       '3. a dictionary \n'\
                       '4. list \n\n' + METATADATA_FILE_FORMAT
    process = subprocess.run(["vcfg", "--vhome", vhome,
                              "update-config-store", "--metadata-file", file_path],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )

    assert process.stdout.decode('utf-8').strip() == expected_message
    assert process.returncode == 1


def test_raw_config_in_single_metafile(monkeypatch, vhome):
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    file_path = os.path.join(vhome, "single_config.json")
    with open(file_path, "w") as f:
        f.write(json.dumps({"agent1": {"config": "string config",
                                       "config-type": "raw"}}))

    process = subprocess.run(["vcfg", "--vhome", vhome,
                              "update-config-store", "--metadata-file", file_path],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )

    assert process.stdout.decode('utf-8').strip() == ''
    assert process.stderr.decode('utf-8').strip() == ''
    assert process.returncode == 0
    store_path = os.path.join(vhome, "configuration_store/agent1.store")
    assert os.path.isfile(store_path)
    with open(store_path) as f:
        store = parse_json_config(f.read())

    assert store["config"]
    assert store["config"]["data"] == "string config"
    assert store["config"]["type"] == "raw"
    initial_modified_time = store["config"]["modified"]

    # now try list of raw config with 1 new and 1 existing
    file_path = os.path.join(vhome, "two_config.json")
    with open(file_path, "w") as f:
        f.write(json.dumps(
            {"agent1": [
                        {"config": "string config", "config-type": "raw"},
                        {"config-name": "new_config", "config-type": "raw", "config": "another string config"}
                       ]
            }
        ))

    process = subprocess.run(["vcfg", "--vhome", vhome,
                              "update-config-store", "--metadata-file", file_path],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )

    assert process.stdout.decode('utf-8').strip() == ''
    assert process.stderr.decode('utf-8').strip() == ''
    assert process.returncode == 0
    store_path = os.path.join(vhome, "configuration_store/agent1.store")
    assert os.path.isfile(store_path)
    with open(store_path) as f:
        store = parse_json_config(f.read())

    assert store["config"]
    assert store["config"]["data"] == "string config"
    assert store["config"]["type"] == "raw"
    assert initial_modified_time == store["config"]["modified"]

    assert store["new_config"]
    assert store["new_config"]["data"] == "another string config"
    assert store["new_config"]["type"] == "raw"
    assert store["new_config"]["modified"]
    assert store["new_config"]["modified"] != initial_modified_time


def test_json_config_in_single_metafile(monkeypatch, vhome):
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    json_data = {"config_key1": "config_value1"}
    file_path = os.path.join(vhome, "single_config.json")
    with open(file_path, "w") as f:
        f.write(json.dumps({"agent2": {"config": json_data,
                                       "config-type": "json"}}))

    process = subprocess.run(["vcfg", "--vhome", vhome,
                              "update-config-store", "--metadata-file", file_path],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )

    assert process.stdout.decode('utf-8').strip() == ''
    assert process.stderr.decode('utf-8').strip() == ''
    assert process.returncode == 0
    store_path = os.path.join(vhome, "configuration_store/agent2.store")
    assert os.path.isfile(store_path)
    with open(store_path) as f:
        store = parse_json_config(f.read())

    assert store["config"]
    assert parse_json_config(store["config"]["data"]) == json_data
    assert store["config"]["type"] == "json"
    initial_modified_time = store["config"]["modified"]


def test_csv_configfile_in_single_metafile(monkeypatch, vhome):
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    csv_file = os.path.join(vhome, "config.csv")
    csv_str = "point_name,type\npoint1,boolean\npoint2,int"
    csv_list = [{"point_name": "point1", "type": "boolean"}, {"point_name": "point2", "type": "int"}]
    with open(csv_file, "w") as f:
        f.write(csv_str)
    file_path = os.path.join(vhome, "single_config.json")
    with open(file_path, "w") as f:
        f.write(json.dumps({"agent3": {"config": csv_file,
                                       "config-type": "csv"}}))

    process = subprocess.run(["vcfg", "--vhome", vhome,
                              "update-config-store", "--metadata-file", file_path],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )

    assert process.stdout.decode('utf-8').strip() == ''
    assert process.stderr.decode('utf-8').strip() == ''
    assert process.returncode == 0
    store_path = os.path.join(vhome, "configuration_store/agent3.store")
    assert os.path.isfile(store_path)
    with open(store_path) as f:
        store = parse_json_config(f.read())

    assert store["config"]
    f = StringIO(store["config"]["data"])
    csv_list_in_store = [x for x in DictReader(f)]
    assert csv_list_in_store == csv_list
    assert store["config"]["type"] == "csv"
    initial_modified_time = store["config"]["modified"]


def test_single_metafile_two_agent(monkeypatch, vhome):
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    file_path = os.path.join(vhome, "single_config.json")
    with open(file_path, "w") as f:
        f.write(json.dumps(
            {"agent1": {"config": "string config", "config-type": "raw"},
             "agent2": [
                        {"config": "string config", "config-type": "raw"},
                        {"config-name": "new_config", "config-type": "raw", "config": "another string config"}
                       ]
            }))

    process = subprocess.run(["vcfg", "--vhome", vhome,
                              "update-config-store", "--metadata-file", file_path],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )

    assert process.stdout.decode('utf-8').strip() == ''
    assert process.stderr.decode('utf-8').strip() == ''
    assert process.returncode == 0
    store_path = os.path.join(vhome, "configuration_store/agent1.store")
    assert os.path.isfile(store_path)
    with open(store_path) as f:
        store = parse_json_config(f.read())

    assert store["config"]
    assert store["config"]["data"] == "string config"
    assert store["config"]["type"] == "raw"
    assert store["config"]["modified"]

    store_path = os.path.join(vhome, "configuration_store/agent2.store")
    assert os.path.isfile(store_path)
    with open(store_path) as f:
        store = parse_json_config(f.read())

    assert store["config"]
    assert store["config"]["data"] == "string config"
    assert store["config"]["type"] == "raw"
    assert store["config"]["modified"]

    assert store["new_config"]
    assert store["new_config"]["data"] == "another string config"
    assert store["new_config"]["type"] == "raw"
    assert store["new_config"]["modified"]


def test_two_metafile(monkeypatch, vhome):
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    file_path1 = os.path.join(vhome, "meta1.json")
    with open(file_path1, "w") as f:
        f.write(json.dumps({"agent1": {"config": "string config", "config-type": "raw"}}))
    file_path2 = os.path.join(vhome, "meta2.json")
    with open(file_path2, "w") as f:
        f.write(json.dumps(
            {"agent2": [
                        {"config": "string config", "config-type": "raw"},
                        {"config-name": "new_config", "config-type": "raw", "config": "another string config"}
                       ]
             }))
    process = subprocess.run(["vcfg", "--vhome", vhome,
                              "update-config-store", "--metadata-file", file_path1, file_path2],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )

    assert process.stdout.decode('utf-8').strip() == ''
    assert process.stderr.decode('utf-8').strip() == ''
    assert process.returncode == 0
    store_path = os.path.join(vhome, "configuration_store/agent1.store")
    assert os.path.isfile(store_path)
    with open(store_path) as f:
        store = parse_json_config(f.read())

    assert store["config"]
    assert store["config"]["data"] == "string config"
    assert store["config"]["type"] == "raw"
    assert store["config"]["modified"]

    store_path = os.path.join(vhome, "configuration_store/agent2.store")
    assert os.path.isfile(store_path)
    with open(store_path) as f:
        store = parse_json_config(f.read())

    assert store["config"]
    assert store["config"]["data"] == "string config"
    assert store["config"]["type"] == "raw"
    assert store["config"]["modified"]

    assert store["new_config"]
    assert store["new_config"]["data"] == "another string config"
    assert store["new_config"]["type"] == "raw"
    assert store["new_config"]["modified"]


def test_meta_dir(monkeypatch, vhome):
    monkeypatch.setenv("VOLTTRON_HOME", vhome)
    meta_dir = os.path.join(vhome, "meta_dir")
    os.mkdir(meta_dir)
    file_path1 = os.path.join(meta_dir, "meta1.json")
    with open(file_path1, "w") as f:
        f.write(json.dumps({"agent1": {"config": "string config", "config-type": "raw"}}))
    file_path2 = os.path.join(meta_dir, "meta2.json")
    with open(file_path2, "w") as f:
        f.write(json.dumps(
            {"agent2": [
                        {"config": "string config", "config-type": "raw"},
                        {"config-name": "new_config", "config-type": "raw", "config": "another string config"}
                       ]
             }))
    process = subprocess.run(["vcfg", "--vhome", vhome,
                              "update-config-store", "--metadata-file", meta_dir],
                             env=os.environ,
                             cwd=os.environ.get("VOLTTRON_ROOT"),
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE
                             )

    assert process.stdout.decode('utf-8').strip() == ''
    assert process.stderr.decode('utf-8').strip() == ''
    assert process.returncode == 0
    store_path = os.path.join(vhome, "configuration_store/agent1.store")
    assert os.path.isfile(store_path)
    with open(store_path) as f:
        store = parse_json_config(f.read())

    assert store["config"]
    assert store["config"]["data"] == "string config"
    assert store["config"]["type"] == "raw"
    assert store["config"]["modified"]

    store_path = os.path.join(vhome, "configuration_store/agent2.store")
    assert os.path.isfile(store_path)
    with open(store_path) as f:
        store = parse_json_config(f.read())

    assert store["config"]
    assert store["config"]["data"] == "string config"
    assert store["config"]["type"] == "raw"
    assert store["config"]["modified"]

    assert store["new_config"]
    assert store["new_config"]["data"] == "another string config"
    assert store["new_config"]["type"] == "raw"
    assert store["new_config"]["modified"]

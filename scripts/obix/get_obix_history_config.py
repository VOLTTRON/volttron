# -*- coding: utf-8 -*- {{{
# vim: set fenc=utf-8 ft=python sw=4 ts=4 sts=4 et:
#
# Copyright 2020, Battelle Memorial Institute.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# This material was prepared as an account of work sponsored by an agency of
# the United States Government. Neither the United States Government nor the
# United States Department of Energy, nor Battelle, nor any of their
# employees, nor any jurisdiction or organization that has cooperated in the
# development of these materials, makes any warranty, express or
# implied, or assumes any legal liability or responsibility for the accuracy,
# completeness, or usefulness or any information, apparatus, product,
# software, or process disclosed, or represents that its use would not infringe
# privately owned rights. Reference herein to any specific commercial product,
# process, or service by trade name, trademark, manufacturer, or otherwise
# does not necessarily constitute or imply its endorsement, recommendation, or
# favoring by the United States Government or any agency thereof, or
# Battelle Memorial Institute. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY operated by
# BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830
# }}}

from xml.dom.minidom import parseString
import requests
import argparse
import getpass
import csv

parser = argparse.ArgumentParser(description='Create Obix driver configurations for site.')
parser.add_argument('url', default="", help='Url of the exports on the site')
parser.add_argument('csvfile', nargs='?', type=argparse.FileType('w'),
                    default=sys.stdout, help="Output file for register CSV configuration.")
parser.add_argument('devicefile', nargs='?', type=argparse.FileType('w'),
                    default=sys.stdout, help="Output file for device configuration.")
parser.add_argument('-u', '--username', default="",
                    help='Username for site log in.')
parser.add_argument('-p', '--password', default="",
                    help='Password for site log in.')
parser.add_argument('-d', '--device-name', default="",
                    help="Default device name for 'Device Name' column.")


args = parser.parse_args()

username=args.username
password=args.password
url=args.url
device_name = args.device_name

while not username:
    username = input("Username: ")

while not password:
    password = getpass.getpass("Password: ")

if not url.endswith("/"):
    url += '/'

csv_file = csv.DictWriter(args.csvfile,
                          ["Device Name", "Volttron Point Name", "Obix Name"])

csv_file.writeheader()

result = requests.get(url,
                      auth=(username, password))

document = parseString(result.text)
elements = document.getElementsByTagName("ref")

def get_csv_row(element):
    result = {}

    name = element.getAttribute("name").replace("$20", " ").replace("$2d", "-")
    result["Volttron Point Name"] = result["Obix Name"] = name

    result["Device Name"] = device_name

    return result


for e in elements:
    row = get_csv_row(e)

    csv_file.writerow(row)


config = {
  "url": url,
  "username": username,
  "password": password,
  # Interval to query interface for updates in minutes.
  # History points are only published if new data is available
  # config points are gathered and published at this interval.
  "check_interval": 15,
  # Path prefix for all publishes
  "path_prefix": "devices/obix/history/",
  "register_config": "config://obix_h.csv"
}

jsonapi.dump(config, args.devicefile, indent=4)



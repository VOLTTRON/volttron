# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

from xml.dom.minidom import parseString
import requests
import argparse
import getpass
import csv
import sys

from volttron.platform import jsonapi

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


args = parser.parse_args()

username=args.username
password=args.password
url=args.url

while not username:
    username = input("Username: ")

while not password:
    password = getpass.getpass("Password: ")

if not url.endswith("/"):
    url += '/'

csv_file = csv.DictWriter(args.csvfile,
                          ["Volttron Point Name", "Obix Point Name",
                           "Obix Type", "Units", "Writable", "Notes"])

csv_file.writeheader()


result = requests.get(url,
                      auth=(username, password))

document = parseString(result.text)
elements = document.getElementsByTagName("ref")

def get_csv_row(element):
    result = {}

    name = element.getAttribute("name")
    href = element.getAttribute("href")
    query_result = requests.get(url + href,
                          auth=(username, password))
    d = parseString(query_result.text)
    e = d.documentElement
    obix_type = e.tagName
    unit = e.getAttribute("unit")
    if unit:
        unit = unit.split('/')[-1]

    result["Volttron Point Name"] = result["Obix Point Name"] = name
    result["Obix Type"] = obix_type
    result["Units"] = unit
    result["Writable"] = "FALSE"
    notes = []

    precision = e.getAttribute("precision")
    min_value = e.getAttribute("min")
    max_value = e.getAttribute("max")

    if precision:
        notes.append("Precision: " + str(precision))

    if min_value:
        notes.append("Min: " + str(min_value))

    if max_value:
        notes.append("Max: " + str(max_value))

    notes = ", ".join(notes)

    result["Notes"] = notes

    return result


for e in elements:
    row = get_csv_row(e)

    csv_file.writerow(row)

config = {
    "driver_config": {"url": url,
                      "username": username,
                      "password": password},
    "driver_type": "obix",
    "registry_config":"config://obix.csv",
    "interval": 	60,
    "timezone": "UTC"
}

jsonapi.dump(config, args.devicefile, indent=4)

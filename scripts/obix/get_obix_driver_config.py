# Copyright (c) 2018, Battelle Memorial Institute
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
#
# This material was prepared as an account of work sponsored by an
# agency of the United States Government.  Neither the United States
# Government nor the United States Department of Energy, nor Battelle,
# nor any of their employees, nor any jurisdiction or organization
# that has cooperated in the development of these materials, makes
# any warranty, express or implied, or assumes any legal liability
# or responsibility for the accuracy, completeness, or usefulness or
# any information, apparatus, product, software, or process disclosed,
# or represents that its use would not infringe privately owned rights.
#
# Reference herein to any specific commercial product, process, or
# service by trade name, trademark, manufacturer, or otherwise does
# not necessarily constitute or imply its endorsement, recommendation,
# r favoring by the United States Government or any agency thereof,
# or Battelle Memorial Institute. The views and opinions of authors
# expressed herein do not necessarily state or reflect those of the
# United States Government or any agency thereof.
#
# PACIFIC NORTHWEST NATIONAL LABORATORY
# operated by BATTELLE for the UNITED STATES DEPARTMENT OF ENERGY
# under Contract DE-AC05-76RL01830

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





'''

Thermostat Interface:

API to set and get values for the thermostat over WiFi

FakeThermostat - creates a fake thermostat object
ThermostatInterface - creates a real thermostat obect based on address

-Used with RadioThermostatAgent

'''

import json
import sys
import time
import urllib2


class FakeThermostat(object):
    ''' Fake Thermostat: Class that implements the functions used to get
        and set values in a thermostat
    '''
    def __init__(self, url=None):
        self.query = {
            "temp":70.50,
            "tmode":0,
            "fmode":0,
            "override":0,
            "hold":0,
            "t_cool":85.00,
            "t_heat":70.00,
            "time":
                {
                    "day": time.localtime().tm_wday,
                    "hour": time.localtime().tm_hour,
                    "minute": time.localtime().tm_min
                }
        }
        self.success = {"success": 0}
        print "Initialized a Fake Thermostat object"

    def t_cool(self,data):
        ''' Sets cooling setpoint'''
        self.query["t_cool"] = float(data)
        self.query["time"] = {
            "day": time.localtime().tm_wday,
            "hour": time.localtime().tm_hour,
            "minute": time.localtime().tm_min
        }
        return self.success

    def t_heat(self,data):
        ''' Sets heating setpoint'''
        self.query["t_heat"] = float(data)
        self.query["time"] = {
            "day": time.localtime().tm_wday,
            "hour": time.localtime().tm_hour,
            "minute": time.localtime().tm_min
        }
        return self.success

    def tstat(self,):
        ''' Returns current paraments'''

        self.query["time"] = {
            "day": time.localtime().tm_wday,
            "hour": time.localtime().tm_hour,
            "minute": time.localtime().tm_min
        }
        return json.dumps(self.query)
        # return json.loads(query.read().decode("utf-8"))

    def mode(self,data):
        ''' Sets operating mode'''
        self.query["t_mode"] = int(data)
        self.query["time"] = {
            "day": time.localtime().tm_wday,
            "hour": time.localtime().tm_hour,
            "minute": time.localtime().tm_min
        }
        return self.success





def Thermostat_API(url):
    ''' Chooses a Fake device or real device based on url'''
    if url == "Fake":
        return FakeThermostat()
    else :
        return ThermostatInterface(url)


class ThermostatInterface(object):
    '''Base interface to get and set values on the thermostat
    '''
    def __init__(self, url):
        self.urladdress = url

        print "Initialized a REAL Thermostat object"

    def t_setpoint(self,data,point,tmode=''):
        ''' Sets cooling setpoint'''
        if tmode == '':
            msg = { point : data }
        else :
            msg = {"tmode": tmode, point : data}
        value = json.dumps(msg)
        try:
            mode =  (urllib2.urlopen(self.urladdress,value))
            parsed = json.loads(mode.read().decode("utf-8"))
            return json.dumps(parsed)
        except Exception as parsed:
            return parsed

    def t_cool(self,data):
        ''' Sets cooling setpoint'''
        msg = {"tmode":2,"t_cool":data}
        value = json.dumps(msg)
        try:
            mode =  (urllib2.urlopen(self.urladdress,value))
            parsed = json.loads(mode.read().decode("utf-8"))
            return json.dumps(parsed)
        except Exception as parsed:
            return parsed


    def t_heat(self,data):
        ''' Sets heating setpoint'''
        msg = {"tmode":1,"t_heat":data}
        value = json.dumps(msg)
        try:
            mode =  (urllib2.urlopen(self.urladdress,value))
            parsed = json.loads(mode.read().decode("utf-8"))
            return json.dumps(parsed)
        except Exception as parsed:
            return parsed

    def over(self,data):
        ''' Sets override controls'''
        msg = {"override":data}
        value = json.dumps(msg)
        try:
            mode =  (urllib2.urlopen(self.urladdress,value))
            parsed = json.loads(mode.read().decode("utf-8"))
            return json.dumps(parsed)
        except Exception as parsed:
            return parsed

    def hold(self,data):
        ''' Sets  hold controls'''
        msg = {"hold":data}
        value = json.dumps(msg)
        try:
            mode =  (urllib2.urlopen(self.urladdress,value))
            parsed = json.loads(mode.read().decode("utf-8"))
            return json.dumps(parsed)
        except Exception as parsed:
            return parsed

    def model(self):
        ''' Returns device model'''
        address= self.address+"/model"
        try:
            mode =  (urllib2.urlopen(address))
            parsed = json.loads(mode.read().decode("utf-8"))
            return json.dumps(parsed)
        except Exception as parsed:
            return parsed


    def tstat(self):
        ''' Returns current deicve paramenters'''
        try:
            mode =  (urllib2.urlopen(self.urladdress))
            parsed = json.loads(mode.read().decode("utf-8"))
            print json.dumps(parsed)
            return json.dumps(parsed)

        except Exception as parsed:
            return parsed

    def fmode(self,data):
        ''' Sets fan's mode'''
        msg = {"fmode":data}
        value = json.dumps(msg)
        try:
            mode =  (urllib2.urlopen(self.urladdress,value))
            parsed = json.loads(mode.read().decode("utf-8"))
            print json.dumps(parsed)
            return json.dumps(parsed)
        except Exception as parsed:
            return parsed

    def mode(self,data):
        ''' Sets  operating mode'''
        msg = {"tmode":data}
        value = json.dumps(msg)
        try:
            mode =  (urllib2.urlopen(self.urladdress,value))
            parsed = json.loads(mode.read().decode("utf-8"))
            print json.dumps(parsed)
            return json.dumps(parsed)
        except Exception as parsed:
            return parsed

    def energy_led(self,point,data=''):
        '''  Controls energy led'''
        url = self.urladdress+"/led"
        msg = { "energy_led" :data}
        value = json.dumps(msg)
        try:
            mode =  (urllib2.urlopen(url))
            parsed = json.loads(mode.read().decode("utf-8"))
            print json.dumps(parsed)
            return json.dumps(parsed)
        except Exception as parsed:
            return parsed



    def save_energy(self,point='',data=''):
        '''  energy svaing feature'''
        url = self.urladdress+"/save_energy"
        if data == '':
            try:
                mode =  (urllib2.urlopen(url))
                parsed = json.loads(mode.read().decode("utf-8"))
                print json.dumps(parsed)
                return json.dumps(parsed)
            except Exception as parsed:
                return parsed
        else:
            msg = { point : data}
            value = json.dumps(msg)
            try:
                mode =  (urllib2.urlopen(url))
                parsed = json.loads(mode.read().decode("utf-8"))
                print json.dumps(parsed)
                return json.dumps(parsed)
            except Exception as parsed:
                return parsed





    def get_heat_pgm(self,day=''):
        ''' get heat program for a week or a specific day
            day = {'mon','tue','wed','thu','fri','sat','sun'}

            for a specific day, say thursday:
            t.get_heat_pgm('thu')

            for a week:
            t.get_heat_pgm()

        '''
        if day =='':
            url = self.urladdress+"/program/heat"
        else:
            url = self.urladdress+"/program/heat/"+str(day)
        try:
            mode =  (urllib2.urlopen(url))
            parsed = json.loads(mode.read().decode("utf-8"))
            print json.dumps(parsed)
            return json.dumps(parsed)

        except Exception as parsed:
            return parsed


    def get_cool_pgm(self,day=''):
        ''' get cool program for a week or a specific day
            day = {'mon','tue','wed','thu','fri','sat','sun'}

            for a specific day, say thursday:
            t.get_cool_pgm('thu')

            for a week:
            t.get_cool_pgm()

        '''
        if day =='':
            url = self.urladdress+"/program/cool"
        else:
            url = self.urladdress+"/program/cool/"+str(day)
        try:
            mode =  (urllib2.urlopen(url))
            parsed = json.loads(mode.read().decode("utf-8"))
            print json.dumps(parsed)
            return json.dumps(parsed)

        except Exception as parsed:
            return parsed

    def set_cool_pgm(self,schedule,day=''):
        ''' set cool program for a week or a specific day
            day = {'mon','tue','wed','thu','fri','sat','sun'}

            for a spefic day, say 'thu'
            t.set_cool_pgm('{"3":[360, 80, 480, 80, 1080, 80, 1320 , 80]}','thu')

            t.set_cool_pgm('{
                        "1": [360, 70, 480, 70, 1080, 70, 1320, 70],
                        "0": [360, 66, 480, 58, 1080, 66, 1320, 58],
                        "3": [360, 66, 480, 58, 1080, 66, 1320, 58],
                        "2": [360, 66, 480, 58, 1080, 66, 1320, 58],
                        "5": [360, 66, 480, 58, 1080, 66, 1320, 58],
                        "4": [360, 66, 480, 58, 1080, 66, 1320, 58],
                        "6": [360, 66, 480, 58, 1080, 66, 1320, 58]
                 }')
        '''
        if day =='':
            url = self.urladdress+"/program/cool"
        else:
            url = self.urladdress+"/program/cool/"+str(day)
        try:
            mode =  (urllib2.urlopen(url,schedule))
            parsed = json.loads(mode.read().decode("utf-8"))
            print json.dumps(parsed)
            return json.dumps(parsed)

        except Exception as parsed:
            return parsed


    def set_heat_pgm(self,schedule,day=''):
        ''' set heat program for a week or a specific day
            day = {'mon','tue','wed','thu','fri','sat','sun'}

            for a spefic day, say 'thu'
            t.set_heat_pgm('{"3":[360, 80, 480, 80, 1080, 80, 1320 , 80]}','thu')

            for a week
            t.set_heat_pgm('{
                        "1": [360, 70, 480, 70, 1080, 70, 1320, 70],
                        "0": [360, 66, 480, 58, 1080, 66, 1320, 58],
                        "3": [360, 66, 480, 58, 1080, 66, 1320, 58],
                        "2": [360, 66, 480, 58, 1080, 66, 1320, 58],
                        "5": [360, 66, 480, 58, 1080, 66, 1320, 58],
                        "4": [360, 66, 480, 58, 1080, 66, 1320, 58],
                        "6": [360, 66, 480, 58, 1080, 66, 1320, 58]
                 }')
        '''
        if day =='':
            url = self.urladdress+"/program/heat"
        else:
            url = self.urladdress+"/program/heat/"+str(day)
        try:
            mode =  (urllib2.urlopen(url,schedule))
            parsed = json.loads(mode.read().decode("utf-8"))
            print json.dumps(parsed)
            return json.dumps(parsed)

        except Exception as parsed:
            return parsed

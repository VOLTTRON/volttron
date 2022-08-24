import service as cps
import suds
import io

station_csv = {
    'stationID': u'stationID,stationID,StationRegister,,string,Format similar to 1:00001,,FALSE,\n',
    'stationManufacturer': u'stationManufacturer,stationManufacturer,StationRegister,,string,String,,FALSE,\n',
    'stationModel': u'stationModel,stationModel,StationRegister,,string,String,,FALSE,\n',
    'stationMacAddr': u'stationMacAddr,stationMacAddr,StationRegister,,string,String (colon separated mac address),,'
                      u'FALSE,\n',
    'stationSerialNum': u'stationSerialNum,stationSerialNum,StationRegister,,string,String,,FALSE,\n',
    'Address': u'Address,Address,StationRegister,,string,String,,FALSE,\n',
    'City': u'City,City,StationRegister,,string,String,,FALSE,\n',
    'State': u'State,State,StationRegister,,string,String,,FALSE,\n',
    'Country': u'Country,Country,StationRegister,,string,String,,FALSE,\n',
    'postalCode': u'postalCode,postalCode,StationRegister,,string,US Postal code,,FALSE,\n',
    'numPorts': u'numPorts,numPorts,StationRegister,,int,Integer,,FALSE,Number of Ports\n',
    'Type': u'Type,Type,StationRegister,,int,Integer or None,,FALSE,\n',
    'startTime': u'startTime,startTime,StationRegister,,datetime,Datetime,,FALSE,\n',
    'endTime': u'endTime,endTime,StationRegister,,datetime,Datetime,,FALSE,\n',
    'minPrice': u'minPrice,minPrice,StationRegister,,float,Dollar Amount,,FALSE,\n',
    'maxPrice': u'maxPrice,maxPrice,StationRegister,,float,Dollar Amount,,FALSE,\n',
    'unitPricePerHour': u'unitPricePerHour,unitPricePerHour,StationRegister,,float,Dollar Amount,,FALSE,\n',
    'unitPricePerSession': u'unitPricePerSession,unitPricePerSession,StationRegister,,float,Dollar Amount,,FALSE,\n',
    'unitPricePerKWh': u'unitPricePerKWh,unitPricePerKWh,StationRegister,,float,Dollar Amount,,FALSE,\n',
    'unitPriceForFirst': u'unitPriceForFirst,unitPriceForFirst,StationRegister,,float,Dollar Amount,,FALSE,\n',
    'unitPricePerHourThereafter': u'unitPricePerHourThereafter,unitPricePerHourThereafter,StationRegister,'
                                  u',float,Dollar Amount,,FALSE,\n',
    'sessionTime': u'sessionTime,sessionTime,StationRegister,,datetime,,,FALSE,\n',
    'mainPhone': u'mainPhone,mainPhone,StationRegister,,string,Phone Number,,FALSE,\n',
    'orgID': u'orgID,orgID,StationRegister,,string,,,FALSE,\n',
    'organizationName': u'organizationName,organizationName,StationRegister,,string,,,FALSE,\n',
    'sgID': u'sgID,sgID,StationRegister,,string,,,FALSE,\n',
    'sgName': u'sgName,sgName,StationRegister,,string,,,FALSE,\n',
    'currencyCode': u'currencyCode,currencyCode,StationRegister,,string,,,FALSE,\n',
}
station_list = ['stationID', 'stationManufacturer', 'stationModel', 'stationMacAddr', 'stationSerialNum', 'Address',
                'City', 'State', 'Country', 'postalCode', 'numPorts', 'Type', 'startTime', 'endTime', 'minPrice',
                'maxPrice', 'unitPricePerHour', 'unitPricePerSession', 'unitPricePerKWh', 'unitPriceForFirst',
                'unitPricePerHourThereafter', 'sessionTime', 'mainPhone', 'orgID', 'organizationName', 'sgID',
                'sgName', 'currencyCode']

station_port_csv = {
    'portNumber': u'portNumber{port},portNumber,StationRegister,{port},string,Integer,,FALSE,\n',
    'Lat': u'Lat{port},Lat,StationRegister,{port},float,Latitude Coordinate,,FALSE,\n',
    'Long': u'Long{port},Long,StationRegister,{port},float,Longitude Coordinate,,FALSE,\n',
    'Reservable': u'Reservable{port},Reservable,StationRegister,{port},bool,T/F,,FALSE,\n',
    'Level': u'Level{port},Level,StationRegister,{port},string,"L1, L2, L3",,FALSE,\n',
    'Mode': u'Mode{port},Mode,StationRegister,{port},int,"1,2,3",,FALSE,\n',
    'Voltage': u'Voltage{port},Voltage,StationRegister,{port},float,Configured Voltage,,FALSE,\n',
    'Current': u'Current{port},Current,StationRegister,{port},float,Configured Current,,FALSE,\n',
    'Power': u'Power{port},Power,StationRegister,{port},float,Configured Power,,FALSE,Power supported (kW).\n',
    'Connector': u'Connector{port},Connector,StationRegister,{port},string,,,FALSE,'
                 u'"Connector type. For example: NEMA 5-20R, J1772, ALFENL3, "\n',
    'Description': u'Description{port},Description,StationRegister,{port},string,String,,FALSE,\n',
}
station_port_list = ['portNumber', 'Lat', 'Long', 'Reservable', 'Level', 'Mode', 'Voltage', 'Current', 'Power',
                     'Description']

station_status_csv = {
    'Status': u'Status{port},Status,StationStatusRegister,{port},string,,,FALSE,'
              u'"AVAILABLE, INUSE, UNREACHABLE, UNKNOWN"\n',
    'TimeStamp': u'TimeStamp{port},TimeStamp,StationStatusRegister,{port},datetime,,,FALSE,'
                 u'Timestamp of the last communication between the station and ChargePoint\n',
}
station_status_list = ['Status', 'TimeStamp']

shed_load_csv = {
    'shedState': u'shedState{port},shedState,LoadRegister,{port},integer,0 or 1,0,TRUE,'
                 u'True when load shed limits are in place\n',
    'portLoad': u'portLoad{port},portLoad,LoadRegister,{port},float,kw,,FALSE,Load in kw\n',
    'allowedLoad': u'allowedLoad{port},allowedLoad,LoadRegister,{port},float,kw,,TRUE,'
                   u'Allowed load in kw when shedState is True\n',
    'percentShed': u'percentShed{port},percentShed,LoadRegister,{port},integer,percent,,TRUE,'
                   u'Percent of max power shed when shedState is True\n',
}
shed_load_list = ['shedState', 'portLoad', 'allowedLoad', 'percentShed']

alarm_csv = {
    'alarmType': u'alarmType{port},alarmType,AlarmRegister,{port},string,,,FALSE,eg. GFCI Trip\n',
    'alarmTime': u'alarmTime{port},alarmTime,AlarmRegister,{port},datetime,,,FALSE,\n',
    'clearAlarms': u'clearAlarms{port},clearAlarms,AlarmRegister,{port},int,,,TRUE,'
                   u'Sends the clearAlarms query when set to True\n',
}
alarm_list = ['alarmType', 'alarmTime', 'clearAlarms']

charging_session_csv = {
    'sessionID': u'sessionID,sessionID,ChargingSessionRegister,,string,,,FALSE,\n',
    'startTime': u'startTime,startTime,ChargingSessionRegister,,datetime,,,FALSE,\n',
    'endTime': u'endTime,endTime,ChargingSessionRegister,,datetime,,,FALSE,\n',
    'Energy': u'Energy,Energy,ChargingSessionRegister,,float,,,FALSE,\n',
}
charging_session_list = ['sessionID', 'startTime', 'endTime', 'Energy']

station_rights_csv = {
    'stationRightsProfile': u'stationRightsProfile,stationRightsProfile,StationRightsRegister,,dictionary,,,FALSE,'
                            u'"Dictionary of sgID, rights name tuples."\n',
}
station_rights_list = ['stationRightsProfile']

if __name__ == '__main__':
    username = input('API Username: ')
    password = input('API Password: ')

    service = cps.CPService(username=username, password=password)

    try:
        service.getCPNInstances()
        print("Congratulations! Your API credentials are valid.")

        cp_station = input('To generate a CSV, please input a Chargepoint Station ID: ')
        if service.getStations(stationID=cp_station).responseCode == "100":
            with io.open('newFile.csv', 'w') as f:
                f.write(u'Volttron Point Name,Attribute Name,Register Name,Port #,'
                        u'Type,Units,Starting Value,Writable,Notes\n')

                station_response = service.getStations(stationID=cp_station)
                station_rights_response = service.getStationRights(stationID=cp_station)
                station_status_response = service.getStationStatus(cp_station)
                shed_load_response = service.getLoad(stationID=cp_station)
                alarm_response = service.getAlarms(stationID=cp_station)
                charging_session_response = service.getChargingSessionData(stationID=cp_station)

                for attr in station_list:
                    if getattr(station_response, attr)()[0] is not None:
                        f.write(station_csv[attr])

                for attr in alarm_list:
                    try:
                        if getattr(alarm_response, attr)()[0] is not None:
                            f.write(alarm_csv[attr].format(port=''))
                        elif attr == 'clearAlarms':
                            f.write(alarm_csv[attr].format(port=''))
                    except cps.CPAPIException as exception:
                        if alarm_response.responseCode == '153':
                            f.write(alarm_csv[attr].format(port=''))
                        else:
                            continue

                for attr in charging_session_list:
                    if getattr(charging_session_response, attr)()[0] is not None:
                        f.write(charging_session_csv[attr])

                # Station Rights are slightly different.
                for attr in station_rights_list:
                    if getattr(station_rights_response, 'rights')[0] is not None:
                        f.write(station_rights_csv[attr])

                for port in range(1, station_response.numPorts()[0]+1):
                    for attr in station_port_list:
                        if getattr(station_response, attr)(port)[0] is not None:
                            f.write(station_port_csv[attr].format(port=port))

                    for attr in shed_load_list:
                        if getattr(shed_load_response, attr)(port)[0] is not None:
                            f.write(shed_load_csv[attr].format(port=port))

                    for attr in station_status_list:
                        if getattr(station_status_response, attr)(port)[0] is not None:
                            f.write(station_status_csv[attr].format(port=port))

                    for attr in alarm_list:
                        try:
                            if getattr(alarm_response, attr)(port)[0] is not None:
                                f.write(alarm_csv[attr].format(port=port))
                            elif attr == 'clearAlarms':
                                f.write(alarm_csv[attr].format(port=port))
                        except cps.CPAPIException as exception:
                            if alarm_response.responseCode == '153':
                                f.write(alarm_csv[attr].format(port=port))
                            else:
                                continue

        elif service.getStations(stationID=cp_station).responseCode == "102":
            print("No station {0} found.".format(cp_station))
        else:
            print("Some other error happened")

    except suds.WebFault as a:
        print("Sorry, your API credentials are invalid. Please contact Chargepoint for assistance.")

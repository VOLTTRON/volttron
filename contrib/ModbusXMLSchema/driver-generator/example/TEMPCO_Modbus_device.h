#ifndef __TEMPCO_MODBUS_DEVICE_H__
#define __TEMPCO_MODBUS_DEVICE_H__

#include "mdl.h"

/* TEMPCO Modbus device
   This is a description of the TEMPCO modbus device */
class TEMPCO_Modbus_device {
public: 
   /* Connect to a serial device */
   TEMPCO_Modbus_device(int deviceID, const char* serial_port, int baud, char parity='N', int data_bit=8, int stop_bit=1);

   /* Connect to a TCP/IP device */
   TEMPCO_Modbus_device(const char* addr, int port);

   /* Close any open connection and delete the device */
   ~TEMPCO_Modbus_device();

   /* Spare */

   /* Relay1 manual output value */
   int8 fan_relay_on();
   void set_fan_relay_on(int8 arg);

   /* Relay2 manual output value */
   int8 cooling_stage1_relay_on();
   void set_cooling_stage1_relay_on(int8 arg);

   /* Relay3 manual output value */
   int8 cooling_stage2_relay_on();
   void set_cooling_stage2_relay_on(int8 arg);

   /* Relay4 manual output value */
   int8 heating_stage1_relay_on();
   void set_heating_stage1_relay_on(int8 arg);

   /* Relay5 manual output value */
   int8 heating_stage2_relay_on();
   void set_heating_stage2_relay_on(int8 arg);

   /* PID2 Occupied Setpoint */
   int16 temperature_set_point();
   void set_temperature_set_point(int16 arg);

private: 
   modbus_t *md;
   uint16_t r[7];
};

#endif

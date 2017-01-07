#include "TEMPCO_Modbus_device.h"
#include <cerrno>

TEMPCO_Modbus_device::TEMPCO_Modbus_device(int deviceID, const char* serial_port, int baud, char parity, int data_bit, int stop_bit) { 
   errno = 0;
   md = modbus_new_rtu(serial_port,baud,parity,data_bit,stop_bit);
   if (md == NULL) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
   if (modbus_set_slave(md,deviceID) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
   if (modbus_connect(md) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
}

TEMPCO_Modbus_device::TEMPCO_Modbus_device(const char* addr, int port) { 
   errno = 0;
   md = modbus_new_tcp(addr,port);
   if (md == NULL) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
   if (modbus_connect(md) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
}

TEMPCO_Modbus_device::~TEMPCO_Modbus_device() { 
   if (md != NULL) {
      modbus_close(md);
      modbus_free(md);
   }
}


/* Spare */

/* Relay1 manual output value */
int8 TEMPCO_Modbus_device::fan_relay_on() {
   int8 arg;
   errno = 0;
   if (modbus_read_registers(md,255,0,r) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
   arg = (float)(r1) * 1; 
   return arg;
}

void TEMPCO_Modbus_device::set_fan_relay_on(int8 arg) {
   Enter write function code snippet here or adding a user defined csv column and add parsing logic
   errno = 0;
   if (modbus_write_registers(md,255,0,r) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
}


/* Relay2 manual output value */
int8 TEMPCO_Modbus_device::cooling_stage1_relay_on() {
   int8 arg;
   errno = 0;
   if (modbus_read_registers(md,256,0,r) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
   Enter read function code snippet here or adding a user defined csv column and add parsing logic
   return arg;
}

void TEMPCO_Modbus_device::set_cooling_stage1_relay_on(int8 arg) {
   Enter write function code snippet here or adding a user defined csv column and add parsing logic
   errno = 0;
   if (modbus_write_registers(md,256,0,r) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
}


/* Relay3 manual output value */
int8 TEMPCO_Modbus_device::cooling_stage2_relay_on() {
   int8 arg;
   errno = 0;
   if (modbus_read_registers(md,257,0,r) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
   Enter read function code snippet here or adding a user defined csv column and add parsing logic
   return arg;
}

void TEMPCO_Modbus_device::set_cooling_stage2_relay_on(int8 arg) {
   Enter write function code snippet here or adding a user defined csv column and add parsing logic
   errno = 0;
   if (modbus_write_registers(md,257,0,r) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
}


/* Relay4 manual output value */
int8 TEMPCO_Modbus_device::heating_stage1_relay_on() {
   int8 arg;
   errno = 0;
   if (modbus_read_registers(md,258,0,r) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
   Enter read function code snippet here or adding a user defined csv column and add parsing logic
   return arg;
}

void TEMPCO_Modbus_device::set_heating_stage1_relay_on(int8 arg) {
   Enter write function code snippet here or adding a user defined csv column and add parsing logic
   errno = 0;
   if (modbus_write_registers(md,258,0,r) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
}


/* Relay5 manual output value */
int8 TEMPCO_Modbus_device::heating_stage2_relay_on() {
   int8 arg;
   errno = 0;
   if (modbus_read_registers(md,259,0,r) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
   Enter read function code snippet here or adding a user defined csv column and add parsing logic
   return arg;
}

void TEMPCO_Modbus_device::set_heating_stage2_relay_on(int8 arg) {
   Enter write function code snippet here or adding a user defined csv column and add parsing logic
   errno = 0;
   if (modbus_write_registers(md,259,0,r) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
}


/* PID2 Occupied Setpoint */
int16 TEMPCO_Modbus_device::temperature_set_point() {
   int16 arg;
   errno = 0;
   if (modbus_read_registers(md,359,0,r) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
   Enter read function code snippet here or adding a user defined csv column and add parsing logic
   return arg;
}

void TEMPCO_Modbus_device::set_temperature_set_point(int16 arg) {
   Enter write function code snippet here or adding a user defined csv column and add parsing logic
   errno = 0;
   if (modbus_write_registers(md,359,0,r) == -1) {
      throw modbus_exception(errno,modbus_strerror(errno));
   }
}


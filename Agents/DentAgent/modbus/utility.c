#include <stdio.h>
#include <stdint.h>
#include <netinet/in.h>
#include <string.h> 
#include "E30ModbusMsg.h"

#define RCVBUFSIZE 1024

char rxBuf[RCVBUFSIZE];       /* buffer for the reply message */
int rxBufLen = 0;             /* length of reply message */

modbus_reply print_received_msg(uint8_t *buf, int buflen) {
  modbus_reply reply;
  switch (buf[BYTEPOS_MODBUS_FUNC]) {
  case MODBUS_FUNC_READ_REG:
    return print_modbus_reply_read_reg(buf, buflen);

  case MODBUS_FUNC_WRITE_REG:
    return print_modbus_reply_write_reg(buf, buflen);

  case MODBUS_FUNC_WRITE_MULTIREG:
    return print_modbus_reply_write_multireg(buf, buflen);

  case MODBUS_FUNC_REPORT_SLAVEID:
    return print_modbus_reply_report_slaveid(buf, buflen);
  } 
  /* This should not occur!! */
  return reply;
}

modbus_reply print_modbus_reply_read_reg(uint8_t *buf, int buflen) {
  uint8_t byte_cnt;
  int c;
  uint32_t crc_temp;
  modbus_reply_read_reg* reply_msg = (modbus_reply_read_reg*) buf;
  modbus_reply reply;
  reply.modbus_addr = reply_msg->modbus_addr;
  reply.modbus_func = reply_msg->modbus_func;
  reply.modbus_val_bytes = reply_msg->modbus_val_bytes;

  byte_cnt = reply_msg->modbus_val_bytes;

  /* Display registers */
  for (c = 0; c < byte_cnt / 2; c++) {
    reply.modbus_reg_val[c] = (int)((short)ntohs(reply_msg->modbus_reg_val[c]));
  }

  /* Check the CRC in the packet */
  crc_temp = read_crc16((uint8_t*) buf,
                        sizeof(modbus_reply_read_reg) +
                        reply_msg->modbus_val_bytes);
  reply.crc = crc_temp;
  crc_temp = calc_crc16(buf, buflen);

  if (crc_temp != 0) {
      modbus_reply error;
      DieWithError("Invalid CRC recieved: 0x%x, 0x%x", reply.crc, crc_temp);
      memset(&error, 0, sizeof(error));
      return error;
  }
  return reply;
}

modbus_reply print_modbus_reply_write_reg(uint8_t *buf, int buflen) {
  uint32_t crc_temp;
  modbus_reply_write_reg* reply_msg = (modbus_reply_write_reg*) buf;

  modbus_reply reply;
  reply.modbus_addr = reply_msg->modbus_addr;
  reply.modbus_func = reply_msg->modbus_func;
  reply.modbus_reg_addr = reply_msg->modbus_reg_addr;
  reply.modbus_val_bytes = 1;
  reply.modbus_reg_val[0] = ntohs(reply_msg->modbus_reg_val);

  /* Check the CRC in the packet */
  crc_temp = read_crc16((uint8_t*) buf, sizeof(modbus_reply_write_reg));
  reply.crc = crc_temp;
  return reply;
}

modbus_reply print_modbus_reply_write_multireg(uint8_t *buf, int buflen) {
  uint32_t crc_temp;
  modbus_reply reply;
  modbus_reply_write_multireg* reply_msg = (modbus_reply_write_multireg*) buf;

  reply.modbus_addr = reply_msg->modbus_addr;
  reply.modbus_func = reply_msg->modbus_func;
  reply.modbus_reg_addr = reply_msg->modbus_reg_addr;
  reply.modbus_reg_qty = reply_msg->modbus_reg_qty;

  /* Check the CRC in the packet */
  crc_temp = read_crc16((uint8_t*) buf, sizeof(modbus_reply_write_multireg));
  reply.crc = crc_temp;
  return reply;
}


modbus_reply print_modbus_reply_report_slaveid(uint8_t *buf, int buflen) {
  uint32_t crc_temp;
  uint8_t additionalData[80]; /* Buffer for additional data */
  modbus_reply reply;
  modbus_reply_report_slaveid* reply_msg = (modbus_reply_report_slaveid*) buf;

  reply.modbus_addr = (int) reply_msg->modbus_addr;
  reply.modbus_func = reply_msg->modbus_func;
  reply.modbus_val_bytes = reply_msg->modbus_val_bytes;
  reply.modbus_slaveid = reply_msg->modbus_slaveid;
  reply.modbus_run_indicator = reply_msg->modbus_run_indicator;
  reply.modbus_additional = reply_msg->modbus_additional;
  /* Check the CRC in the packet */
  crc_temp = read_crc16((uint8_t*) buf,
                        sizeof(modbus_reply_report_slaveid) +
                        reply_msg->modbus_val_bytes - 2);
  strncpy((char*)additionalData, (char*) reply_msg->modbus_additional,
			reply_msg->modbus_val_bytes - 2);
  reply.crc = crc_temp;
  return reply;
}

int get_val(void *array, int index) {
	int* arr = array;
	return arr[index];
}

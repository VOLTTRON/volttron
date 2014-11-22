#include <stdio.h>      /* for printf() and fprintf() */
#include <sys/socket.h> /* for socket(), connect(), send(), and recv() */
#include <arpa/inet.h>  /* for sockaddr_in and inet_addr() */
#include <stdlib.h>     /* for atoi() and exit() */
#include <string.h>     /* for memset() */
#include <unistd.h>     /* for close() */

#include "E30ModbusMsg.h"

#define RCVBUFSIZE 1024   /* Size of receive buffer */ 

#define ARGS_QUERY  5
#define ARGS_READ   6
#define ARGS_WRITE  7
#define ARGS_WRITEM_REGVAL_POS 7

int prepare_msg_query(char* servIP, uint16_t servPort, uint8_t modbus_addr, char* buf, 
	struct sockaddr_in *pServAddr);
int prepare_msg_read(char* servIP, uint16_t servPort, uint8_t modbus_addr, uint16_t reg_addr, uint16_t reg_qty, /* quantity of registers to read (1-125) */
	char* buf, struct sockaddr_in *pServAddr);
int prepare_msg_write(char* servIP, uint16_t servPort, uint8_t modbus_addr, uint16_t reg_addr, uint16_t reg_val, char* buf,
	struct sockaddr_in *pServAddr);
int prepare_msg_writem(char* servIP, uint16_t servPort, uint8_t modbus_addr, uint16_t reg_addr, uint16_t reg_qty, uint16_t reg_val, char* buf,
	struct sockaddr_in *pServAddr);
modbus_reply execute_command(char *cmd, char* servIP, uint16_t servPort, uint8_t modbus_addr, uint16_t reg_addr, uint16_t reg_qty, uint16_t reg_val);
modbus_reply print_received_msg(uint8_t *buf, int buflen);

modbus_reply dev_query(char* servIP, int servPort, int modbus_addr);
modbus_reply dev_read(char* servIP, int servPort, int modbus_addr, int reg_addr, int reg_qty);
modbus_reply dev_write(char* servIP, int servPort, int modbus_addr, int reg_addr, int reg_val);
modbus_reply dev_writem(char* servIP, int servPort, int modbus_addr, int reg_addr, int reg_qty, int reg_val);
int get_val(void *array, int index);

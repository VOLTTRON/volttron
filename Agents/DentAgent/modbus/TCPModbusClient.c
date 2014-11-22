#include <string.h>
#include <errno.h>
#include <Python.h>

#include "TCPModbusClient.h"

modbus_reply dev_query(char* servIP, int servPort, int modbus_addr)
{
	return execute_command("query", servIP, (uint16_t)servPort, (uint8_t)modbus_addr, 0, 0, 0);
}

modbus_reply dev_read(char* servIP, int servPort, int modbus_addr, int reg_addr, int reg_qty)
{
	return execute_command("read", servIP, (uint16_t)servPort, (uint8_t)modbus_addr, (uint16_t)reg_addr, (uint16_t)reg_qty, 0);
}
modbus_reply dev_write(char* servIP, int servPort, int modbus_addr, int reg_addr, int reg_val)
{
	return execute_command("write", servIP, (uint16_t)servPort, (uint8_t)modbus_addr, (uint16_t)reg_addr, 0, (uint16_t)reg_val);
}

modbus_reply dev_writem(char* servIP, int servPort, int modbus_addr, int reg_addr, int reg_qty, int reg_val)
{
	return execute_command("writem", servIP, (uint16_t)servPort, (uint8_t)modbus_addr, (uint16_t)reg_addr, (uint16_t)reg_qty, (uint16_t)reg_val);
}

modbus_reply execute_command(char *cmd, char* servIP, uint16_t servPort, uint8_t modbus_addr, uint16_t reg_addr, uint16_t reg_qty, uint16_t reg_val)
{
    int sock;                     /* Socket descriptor */
    struct sockaddr_in servAddr;  /* Echo server address */
    char txBuf[RCVBUFSIZE];       /* String to send to echo server */
    char rxBuf[RCVBUFSIZE];       /* Buffer for echo string */ 
    uint32_t txBufLen;            /* Length of string to echo */
    int bytesRcvd;                /* Bytes read in single recv() */ 
    int bytesReply = MODBUS_MIN_REPLY;           /* Length of reply expected. */
    struct timeval timeout;
    modbus_reply error_reply;
    PyThreadState *_save = PyEval_SaveThread();

    memset(&error_reply, 0, sizeof(error_reply));


    txBufLen = 0;

    /* Zero out the server address structure */
    memset(&servAddr, 0, sizeof(servAddr));     

	if (strcmp(cmd, "query") == 0 || strcmp(cmd, "q") == 0) {
      /* Prepare tx buffer for query command */
      txBufLen = prepare_msg_query(servIP, servPort, modbus_addr, txBuf, &servAddr);
    } 
    /* Check arguments for read command */
    else if (strcmp(cmd, "read") == 0 || strcmp(cmd, "r") == 0) {
      /* Prepare tx buffer for read command */
      txBufLen = prepare_msg_read(servIP, servPort, modbus_addr, reg_addr, reg_qty, txBuf, &servAddr); 
    }
    /* Check arguments for write command */
    else if (strcmp(cmd, "write") == 0 || strcmp(cmd, "w") == 0) {
      /* Prepare tx buffer for write command */
      txBufLen = prepare_msg_write(servIP, servPort, modbus_addr, reg_addr, reg_val, txBuf, &servAddr); 
    }
    /* Check arguments for writem command */
    else if (strcmp(cmd, "writem") == 0 || strcmp(cmd, "m") == 0) {
      /* Prepare tx buffer for writem command */
      txBufLen = prepare_msg_writem(servIP, servPort, modbus_addr, reg_addr, reg_qty, reg_val, txBuf, &servAddr); 
    }

    /* Create a reliable, stream socket using TCP */
    if ((sock = socket(PF_INET, SOCK_STREAM, IPPROTO_TCP)) < 0) {
      PyEval_RestoreThread(_save);
      DieWithError("socket() failed");
      return error_reply;
    }

    timeout.tv_sec = 2;
    timeout.tv_usec = 0;
    if (setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO,  &timeout, sizeof(timeout)) < 0) {
      PyEval_RestoreThread(_save);
      DieWithError("setsockopt(): setting timeout failed");
      close(sock);
      return error_reply;
    }

    /* Establish the connection to the echo server */
    if (connect(sock, (struct sockaddr *) &servAddr, sizeof(servAddr)) < 0) {
      PyEval_RestoreThread(_save);
      DieWithError("connect() failed");
      close(sock);
      return error_reply;
    }

    /* Send the string to the server */
    if (send(sock, txBuf, txBufLen, 0) != txBufLen) {
        PyEval_RestoreThread(_save);
        DieWithError("send() sent a different number of bytes than expected");
	close(sock);
        return error_reply;
    }

    bytesRcvd = 0;
    /* Receive the same string back from the server */
    while (bytesRcvd < bytesReply) {
        int n;
        /* Receive up to the buffer size bytes from the sender */
        n = recv(sock, rxBuf + bytesRcvd, RCVBUFSIZE - bytesRcvd - 1, 0);
        if (n < 0) {
            PyEval_RestoreThread(_save);
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                DieWithError("recv() timed out");
            } else {
                DieWithError("recv() failed or connection closed prematurely");
            }
            close(sock);
            return error_reply;
        }
        bytesRcvd += n;

        if (bytesRcvd >= MODBUS_MIN_REPLY) {
            // these include the size of the header structure and crc
            switch (rxBuf[1]) {
            case MODBUS_FUNC_READ_REG:
                bytesReply = 5 + (unsigned char)rxBuf[2];
                break;
            case MODBUS_FUNC_WRITE_REG:
                bytesReply = 8;
                break;
            case MODBUS_FUNC_WRITE_MULTIREG:
                bytesReply = 7 + (unsigned char)rxBuf[2];
                break;
            case MODBUS_FUNC_REPORT_SLAVEID:
                bytesReply = 5 + (unsigned char)rxBuf[2];
                break;
            }
        }
    }
    /* SDH : ? it's not a string...  */
    rxBuf[bytesRcvd] = '\0';  /* Terminate the string! */ 
    if (bytesRcvd < bytesReply) {
        PyEval_RestoreThread(_save);
        DieWithError("failed to read Modbus reply: expecting %i bytes, got %i", 
                     bytesReply, bytesRcvd);
        close(sock);
        return error_reply;
    }

    close(sock);
    PyEval_RestoreThread(_save);
    return print_received_msg((uint8_t *)rxBuf, bytesRcvd);
}

int prepare_msg_query(char* servIP, uint16_t servPort, uint8_t modbus_addr, char* buf, 
                      struct sockaddr_in *pServAddr) {
  int bufLen;                   /* Length of string to echo */
  uint32_t crc_temp;
  uint32_t crc_offset;
  
  modbus_req_report_slaveid* req_msg = NULL;

  pServAddr->sin_family      = AF_INET;     /* Internet address family */
  pServAddr->sin_addr.s_addr = inet_addr(servIP); /* Server IP address */
  pServAddr->sin_port        = htons(servPort);   /* Server port */

  req_msg = (modbus_req_report_slaveid*) buf;
  req_msg->modbus_addr = modbus_addr;
  req_msg->modbus_func = MODBUS_FUNC_REPORT_SLAVEID;

  /* Calculate CRC16 for the request msg */
  crc_offset = sizeof(modbus_req_report_slaveid); 
  crc_temp = calc_crc16((uint8_t*) buf, crc_offset); 
  buf[crc_offset]   = (uint8_t) crc_temp & 0x0ff; /* lower 8bit */
  buf[crc_offset+1] = (uint8_t) (crc_temp >> 8) & 0x0ff;  /* upper 8bit */
  buf[crc_offset+2] = 0; /* end of string */

  bufLen = crc_offset + CRC16_SIZE;

  return bufLen; 
}

int prepare_msg_read(char* servIP, uint16_t servPort, uint8_t modbus_addr, uint16_t reg_addr, uint16_t reg_qty, /* quantity of registers to read (1-125) */
						char* buf, struct sockaddr_in *pServAddr) {
  int bufLen;                   /* Length of string to echo */
  uint32_t crc_temp;
  uint32_t crc_offset;  

  modbus_req_read_reg* req_msg = NULL;

  pServAddr->sin_family      = AF_INET;     /* Internet address family */
  pServAddr->sin_addr.s_addr = inet_addr(servIP); /* Server IP address */
  pServAddr->sin_port        = htons(servPort);   /* Server port */

  if (reg_qty != 0) {
    /* Ensure that reg_qty between 1 to 125. */
    if (reg_qty < MODBUS_REG_READ_QTY_MIN ||
        reg_qty > MODBUS_REG_READ_QTY_MAX) {
      reg_qty = MODBUS_REG_READ_QTY_DEFAULT;
    }
  }
  else {
    reg_qty = MODBUS_REG_READ_QTY_DEFAULT;
  }

  /* Fill in each field of buf */
  req_msg = (modbus_req_read_reg*) buf;
  req_msg->modbus_addr = modbus_addr;
  req_msg->modbus_func = MODBUS_FUNC_READ_REG;
  req_msg->modbus_reg_addr = htons(reg_addr);
  req_msg->modbus_reg_qty  = htons(reg_qty);

  /* Calculate CRC16 for the request msg */
  crc_offset = sizeof(modbus_req_read_reg);
  crc_temp = calc_crc16((uint8_t*) buf, crc_offset);
  buf[crc_offset]   = (uint8_t) crc_temp & 0x0ff; /* lower 8bit */
  buf[crc_offset+1] = (uint8_t) (crc_temp >> 8) & 0x0ff;  /* upper 8bit */
  buf[crc_offset+2] = '\0'; /* end of string */

  bufLen = crc_offset + CRC16_SIZE; 

  return bufLen; 
}

int prepare_msg_write(char* servIP, uint16_t servPort, uint8_t modbus_addr, uint16_t reg_addr, uint16_t reg_val, char* buf,
                      struct sockaddr_in *pServAddr) {
  int bufLen;                   /* Length of string to echo */
  uint32_t crc_temp;
  uint32_t crc_offset;

  modbus_req_write_reg* req_msg      = NULL;

  pServAddr->sin_family      = AF_INET;     /* Internet address family */
  pServAddr->sin_addr.s_addr = inet_addr(servIP); /* Server IP address */
  pServAddr->sin_port        = htons(servPort);   /* Server port */

  /* Fill in each field of buf */
  req_msg = (modbus_req_write_reg*) buf;
  req_msg->modbus_addr = modbus_addr;
  req_msg->modbus_func = MODBUS_FUNC_WRITE_REG;
  req_msg->modbus_reg_addr = htons(reg_addr);
  req_msg->modbus_reg_val  = htons(reg_val);

  /* CRC: first lower 8-bit, then upper 8-bit */
  /* Exception to Big-endianess */
  crc_offset = sizeof(modbus_req_write_reg);
  crc_temp = calc_crc16((uint8_t*) buf, crc_offset);
  buf[crc_offset]   = (uint8_t) crc_temp & 0x0ff; /* lower 8bit */
  buf[crc_offset+1] = (uint8_t) (crc_temp >> 8) & 0x0ff;  /* upper 8bit */
  buf[crc_offset+2] = '\0'; /* end of string */

  bufLen = crc_offset + CRC16_SIZE;

  return bufLen; 
}

int prepare_msg_writem(char* servIP, uint16_t servPort, uint8_t modbus_addr, uint16_t reg_addr, uint16_t reg_qty, uint16_t reg_val, char* buf,
                       struct sockaddr_in *pServAddr) {
  int bufLen;                   /* Length of string to echo */
  uint32_t crc_temp;
  uint32_t crc_offset;
  int c;

  modbus_req_write_multireg* req_msg = NULL;
  
  pServAddr->sin_family      = AF_INET;     /* Internet address family */
  pServAddr->sin_addr.s_addr = inet_addr(servIP); /* Server IP address */
  pServAddr->sin_port        = htons(servPort);   /* Server port */

  /* Test for correct number of register values */
  if( ARGS_WRITEM_REGVAL_POS != reg_qty)  {
    fprintf(stderr, "Usage: %s <Server IP> <Server Port> <Modbus Addr> <Register Addr> <Register Qty> <Val 1> <Val 2> ... \n", servIP);
    fprintf(stderr, "<Register Qty> and number of registers <Val 1>, <Val 2>, ... should match. \n");
    exit(1);
  }

  /* Fill in each field of buf */
  req_msg = (modbus_req_write_multireg*) buf;
  req_msg->modbus_addr = modbus_addr;
  req_msg->modbus_func = MODBUS_FUNC_WRITE_MULTIREG;
  req_msg->modbus_reg_addr = htons(reg_addr);
  req_msg->modbus_reg_qty  = htons(reg_qty);
  req_msg->modbus_val_bytes = (uint8_t) 2 * reg_qty;

  for (c = 0; c < reg_qty; c++) {
//    reg_val = (uint16_t) atoi(argv[ARGS_WRITEM_REGVAL_POS + c]);
    req_msg->modbus_reg_val[c] = htons(reg_val);
  }

  /* CRC: first lower 8-bit, then upper 8-bit */
  /* Exception to Big-endianess */
  crc_offset = sizeof(modbus_req_write_multireg) + 2 * reg_qty;
  crc_temp = calc_crc16((uint8_t*) buf, crc_offset);
  buf[crc_offset]   = (uint8_t) crc_temp & 0x0ff; /* lower 8bit */
  buf[crc_offset+1] = (uint8_t) (crc_temp >> 8) & 0x0ff;  /* upper 8bit */
  buf[crc_offset+2] = '\0'; /* end of string */

  bufLen = crc_offset + CRC16_SIZE;

  return bufLen; 
}

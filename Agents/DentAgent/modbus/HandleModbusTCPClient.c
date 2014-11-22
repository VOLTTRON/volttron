#include <stdio.h>      /* for printf() and fprintf() */
#include <sys/socket.h> /* for recv() and send() */
#include <unistd.h>     /* for close() */
#include <string.h>
#include <stdint.h>
#include <netinet/in.h>
#include "E30ModbusMsg.h"

#define RCVBUFSIZE 1024   /* Size of receive buffer */ 
#define SLAVEID "Veris Model E30A Branch Circuit Monitor, S/N=0x12345678, Location=\"NOT_ASSIGNED\""


void HandleTCPClient(int clntSocket, uint8_t modbus_addr)
{
    char rxBuf[RCVBUFSIZE];    /* Buffer for echo string */
    int recvMsgSize = 0;        /* Size of received message */
    char txBuf[RCVBUFSIZE];  /* Buffer for reply string */
    int replyMsgSize = 0;       /* Size of reply message */

    /* Receive message from client */
    if ((recvMsgSize = recv(clntSocket, rxBuf, RCVBUFSIZE, 0)) < 0)
        DieWithError("recv() failed");

    printf("Message of %d bytes received.\n", recvMsgSize);

    /* Send received string and receive again until end of transmission */
    while (recvMsgSize > 0)      /* zero indicates end of transmission */
    {
        /* Display the received message as hex arrays */
        int c;
        for (c = 0; c < recvMsgSize; c++) {
          printf("%02X ", (uint8_t)*(rxBuf + c)); 
        } 
        printf("\n");

        /* Check the modbus server addr */ 
        if (rxBuf[BYTEPOS_MODBUS_ADDR] == modbus_addr) {
          uint32_t crc_in_packet = 0;
          uint32_t crc_calculated = 0;
          
          /* Check the CRC in the packet */
          crc_in_packet = ((uint8_t) rxBuf[recvMsgSize - 1]) << 8 |
                          ((uint8_t) rxBuf[recvMsgSize - 2]);

          /* Calculate the CRC */
          crc_calculated = calc_crc16((uint8_t*)rxBuf, recvMsgSize - 2) & 0x0ffff;

          if (crc_in_packet == crc_calculated) {

            /* Check the available function codes */
            if (rxBuf[BYTEPOS_MODBUS_FUNC] == MODBUS_FUNC_REPORT_SLAVEID) {
              uint32_t crc_temp = 0;
              uint32_t crc_offset;

              modbus_reply_report_slaveid* replyMsg = 
                (modbus_reply_report_slaveid*) txBuf;

              replyMsg->modbus_addr = modbus_addr;
              replyMsg->modbus_func = MODBUS_FUNC_REPORT_SLAVEID;
              replyMsg->modbus_val_bytes = strlen(SLAVEID) + 2;
              replyMsg->modbus_slaveid = 0xff;
              replyMsg->modbus_run_indicator = 0xff;
              strcpy((char*)replyMsg->modbus_additional, SLAVEID);

              crc_offset = sizeof(modbus_reply_report_slaveid) +
                            strlen(SLAVEID);
              crc_temp = calc_crc16((uint8_t*) txBuf, crc_offset) & 0x0ffff;
              txBuf[crc_offset] = (uint8_t) (crc_temp & 0x0ff);
              txBuf[crc_offset + 1] = (uint8_t) (crc_temp >> 8 & 0x0ff);
              txBuf[crc_offset + 2] = 0;
              replyMsgSize = crc_offset + 2;

              if (send(clntSocket, txBuf, replyMsgSize, 0) != replyMsgSize)
                DieWithError("send() failed");
            }
            else if (rxBuf[BYTEPOS_MODBUS_FUNC] == MODBUS_FUNC_READ_REG) {
              uint32_t crc_temp;
              uint32_t crc_offset;
              uint16_t reg_qty;
              uint16_t cnt;

              modbus_req_read_reg* reqMsg = (modbus_req_read_reg*) rxBuf; 
              modbus_reply_read_reg* replyMsg = (modbus_reply_read_reg*) txBuf;

              reg_qty = ntohs(reqMsg->modbus_reg_qty);

              replyMsg->modbus_addr = modbus_addr;
              replyMsg->modbus_func = MODBUS_FUNC_READ_REG;
              replyMsg->modbus_val_bytes = 2 * reg_qty;
              for (cnt = 0; cnt < reg_qty; cnt++) {
                replyMsg->modbus_reg_val[cnt] = htons(cnt); 
              }
              
              crc_offset = sizeof(modbus_reply_read_reg) + 2 * reg_qty; 
              crc_temp = calc_crc16((uint8_t*) txBuf, crc_offset) & 0x0ffff; 
              txBuf[crc_offset] = (uint8_t) (crc_temp & 0x0ff);
              txBuf[crc_offset + 1] = (uint8_t) (crc_temp >> 8 & 0x0ff);
              txBuf[crc_offset + 2] = 0;
              replyMsgSize = crc_offset + 2;

              if (send(clntSocket, txBuf, replyMsgSize, 0) != replyMsgSize)
                DieWithError("send() failed");
            }
            else {
              printf("Modbus function code %02x not supported!\n", 
                rxBuf[BYTEPOS_MODBUS_FUNC]);
            }
          }
          else {
            printf("CRC does not match!\n");
            printf("CRC in the packet: %02x\n", crc_in_packet & 0x0ffff);
            printf("CRC calculated: %02x\n", crc_calculated & 0x0ffff);
          } 
        }
        else {
          printf("Modbus server address does not match!\n");
          printf("address in the packet: %d\n", rxBuf[BYTEPOS_MODBUS_ADDR]);
          printf("address of this server: %d\n", modbus_addr);
        }

        /* See if there is more data to receive */
        if ((recvMsgSize = recv(clntSocket, rxBuf, RCVBUFSIZE, 0)) < 0)
            DieWithError("recv() failed");
    }

    close(clntSocket);    /* Close client socket */
}

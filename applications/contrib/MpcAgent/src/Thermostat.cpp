#include "Thermostat.h"

Thermostat::Thermostat(const char* IP_addr, int port)
{
	ctx = modbus_new_tcp(IP_addr,port);
	if (ctx == NULL)
	{
		throw ModbusException("Unable to allocate context");
	}
	modbus_set_debug(ctx,TRUE);
	modbus_set_error_recovery(ctx,
		(modbus_error_recovery_mode)(MODBUS_ERROR_RECOVERY_LINK |
		MODBUS_ERROR_RECOVERY_PROTOCOL));
	if (modbus_connect(ctx) == -1)
	{
		modbus_free(ctx);
		ctx = NULL;
		throw ModbusException(modbus_strerror(errno));
	}
}

Thermostat::~Thermostat()
{
	if (ctx != NULL)
	{
		modbus_close(ctx);
		modbus_free(ctx);
	}
}

float Thermostat::temp()
{
	uint16_t dest;
	if (modbus_read_registers(ctx,1,1,&dest) != 1)
	{
		throw ModbusException(modbus_strerror(errno));
	}
	m_temp = (float)dest;
	return m_temp;
}


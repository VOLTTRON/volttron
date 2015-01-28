#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cerrno>
#include <string>
#include <exception>
#include <unistd.h>
#include <modbus.h>

class ModbusException:
	public std::exception
{
	public:
		ModbusException(std::string errMsg):
			std::exception(),
			errMsg(errMsg)
		{
		}
		virtual const char* what() const throw()
		{
			return errMsg.c_str();
		}
		virtual ~ModbusException() throw() {}
	private:
		std::string errMsg;
};

/**
 * Interface to a ModBus thermostat.
 */
class Thermostat
{
	public:
		/**
		 * Connect to a thermostat at the specified address.
		 */
		Thermostat(const char* IP_addr, int port);
		/**
		 * Connection is closed when the thermostat is
		 * deleted.
		 */
		~Thermostat();
		/**
		 * Read temperature and setpoints at the thermostat.
		 */
		float temp();
		float high_temp_limit();
		float low_temp_limit();
		/**
		 * Read and write the HVAC mode.
		 */
		typedef enum { HEAT, COOL, IDLE } hvac_mode_t;
		hvac_mode_t mode();
		void mode(hvac_mode_t hvac_mode);

	private:
    	modbus_t *ctx;
		float m_temp;
};

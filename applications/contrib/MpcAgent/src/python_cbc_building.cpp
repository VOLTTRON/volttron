/**
 * This building library is specifically for the four zone gynasium at
 * the Central Baptist Church.
 */
#include <fstream>
#include <iostream>
#include <time.h>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cerrno>
#include <string>
#include <exception>
#include <pthread.h>
#include <unistd.h>
#include <modbus.h>
#include <cassert>
#include "python_building_interface.h"
using namespace std;

#include <stdio.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

static void millisleep(int millisecs)
{
	timespec tspec;
	tspec.tv_sec = millisecs/1000;
	tspec.tv_nsec = (millisecs-tspec.tv_sec*1000)*1000;
	nanosleep(&tspec,NULL);
}

static const char* gettimestr()
{
	struct timeval tv;
	struct tm* ptm;
	static char time_string[1000];
	/* Obtain the time of day, and convert it to a tm struct.  */
	gettimeofday(&tv,NULL);
	ptm = localtime(&tv.tv_sec);
	/* Format the date and time, down to a single second.  */
	if (ptm != NULL)
		strftime(time_string,999,"%Y-%m-%d %H:%M:%S",ptm);
	else
		sprintf(time_string,"localtime() failed");
	return time_string;
}

/**
 * Exception thrown in response to a MODBUS failure.
 */
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
 * MODBUS over RS232 to TSTAT6 thermostat.
 */
class Thermostat
{
	public:
		/**
		 * Connect to a thermostat at the specified address.
		 */
		Thermostat(unsigned char ModbusDevID);
		/**
		 * Connection is closed when the thermostat is
		 * deleted.
		 */
		~Thermostat();
		/**
		 * Read temperature and setpoints at the thermostat.
		 */
		double temp();
		void temp_limits(volatile double& high, volatile double& low);
		/**
		 * Set the cooling and heating deadbands
		 */
		void set_deadbands(double cool, double heat)
		{
			this->cool_band = cool;
			this->heat_band = heat;
		}
		/**
		 * Set the fan mode
		 */
		void set_fan_mode(int fan_mode)
		{
			fan = fan_mode;
		}
		/**
		 * Read and write the HVAC mode.
		 */
		typedef enum {
			HEAT1 = 0,
			HEAT2 = 1,
			COOL1 = 2,
			COOL2 = 3,
			IDLE = 4,
			UNKNOWN = 5
		} hvac_mode_t;
		hvac_mode_t mode();
		void mode(hvac_mode_t hvac_mode);
		void write_defaults();
		/// Problem with the connection?
		static bool bad() { return isBadState; }
		/// Try to reset the connection
		static void reset();
		static const char* mode_to_str(hvac_mode_t m) { return m_str[m]; }
	private:
		// The serial port is shared by every thermostat
    	static modbus_t *ctx;
		// Because the port is shared, the connection status is also shared
		static bool isBadState;
		// Each thermostat has its own device ID
		const int devID;
		// Heating and cooling bands
		volatile double cool_band, heat_band;
		// Mode = 0 is auto, 1 is on
		volatile int fan;
		void write_reg(int addr, uint16_t data);
		void read_reg(int addr, uint16_t* data);

		static const char* m_str[6];
		static const int
			COOLING1_RELAY,
			COOLING2_RELAY,
			HEATING1_RELAY,
			HEATING2_RELAY,
			FAN_RELAY;
};

bool Thermostat::isBadState = true;
modbus_t* Thermostat::ctx = NULL;
const char* Thermostat::m_str[6] = {"heat1","heat2","cool1","cool2","idle","no data"};
const int Thermostat::FAN_RELAY = 255; 
const int Thermostat::COOLING1_RELAY = 256;
const int Thermostat::COOLING2_RELAY = 257;
const int Thermostat::HEATING1_RELAY = 258;
const int Thermostat::HEATING2_RELAY = 259;

void Thermostat::write_defaults()
{
	// Set to manual control
	write_reg(254,0xffff);
}

void Thermostat::write_reg(int addr, uint16_t data)
{
	if (modbus_set_slave(ctx,devID) != 0)
	{
		isBadState = true;
		throw ModbusException("Unable to set network address");
	}
	if (modbus_write_register(ctx,addr,data) != 1)
	{
		isBadState = true;
		throw ModbusException(modbus_strerror(errno));
	} 
}

void Thermostat::read_reg(int addr, uint16_t* data)
{
	if (modbus_set_slave(ctx,devID) != 0)
	{
		isBadState = true;
		throw ModbusException("Unable to set network address");
	}
	if (modbus_read_registers(ctx,addr,1,data) != 1)
	{
		isBadState = true;
		throw ModbusException(modbus_strerror(errno));
	}
}

Thermostat::Thermostat(unsigned char ModbusDevID):
	devID(ModbusDevID),
	cool_band(2.0),
	heat_band(2.0),
	fan(0)
{
}

void Thermostat::reset()
{
	if (ctx != NULL)
	{
		do
		{
			millisleep(100);
		}
		while (modbus_flush(ctx) > 0);
		modbus_close(ctx);
		modbus_free(ctx);
		ctx = NULL;
	}
	ctx = modbus_new_rtu("/dev/ttyS0",19200,'N',8,1);
	if (ctx == NULL)
	{
		isBadState = true;
		throw ModbusException("Unable to allocate context");
	}
	struct timeval response_timeout;
	response_timeout.tv_sec = 0;
	response_timeout.tv_usec = 1000000; // one second
	modbus_set_response_timeout(ctx, &response_timeout);
	modbus_set_debug(ctx,FALSE);
	if (modbus_connect(ctx) == -1)
	{
		isBadState = true;
		throw ModbusException(modbus_strerror(errno));
	}
	// Ready to go!
	isBadState = false;
}

Thermostat::~Thermostat()
{
	if (ctx != NULL)
	{
		modbus_close(ctx);
		modbus_free(ctx);
		ctx = NULL;
	}
}

double Thermostat::temp()
{
	uint16_t dest;
	read_reg(121,&dest);
	double m_temp = ((double)dest)/10.0;
	return m_temp;
}

void Thermostat::temp_limits(volatile double& high, volatile double& low)
{
	double t;
	uint16_t dest;
	read_reg(345,&dest);
	t = (double)(dest)/10.0;
	high = t + cool_band;
	low = t - heat_band;
}

Thermostat::hvac_mode_t Thermostat::mode()
{
	// Read the relays
	uint16_t c1, c2, h1, h2;
	read_reg(COOLING1_RELAY,&c1); 
	read_reg(HEATING1_RELAY,&h1); 
	read_reg(COOLING2_RELAY,&c2); 
	read_reg(HEATING2_RELAY,&h2); 
	if (h1 == 0 && c1 == 0 && h2 == 0 && c2 == 0)
	{
		return IDLE;
	}
	else if (h1 != 0 && c1 == 0 && c2 == 0)
	{
		if (h2 != 0) return HEAT2;
		else return HEAT1;
	}
	else if (h1 == 0 && c1 != 0 && h2 == 0)
	{
		if (c2 != 0) return COOL2;
		else return COOL1;
	}
	else
	{
		throw ModbusException("heating and cooling active simultaneously");
	}
	return IDLE;
}

void Thermostat::mode(Thermostat::hvac_mode_t m)
{
	if (m == COOL1)
	{
		write_reg(HEATING1_RELAY,0x0000); // Heater 1 off
		write_reg(HEATING2_RELAY,0x0000); // Heater 2 off
		write_reg(COOLING2_RELAY,0x0000); // Cooler 2 off
		write_reg(COOLING1_RELAY,0xffff); // Cooler 1 on
	}
	else if (m == COOL2)
	{
		write_reg(HEATING1_RELAY,0x0000); // Heater 1 off
		write_reg(HEATING2_RELAY,0x0000); // Heater 2 off
		write_reg(COOLING1_RELAY,0xffff); // Cooler 1 on
		write_reg(COOLING2_RELAY,0xffff); // Cooler 2 on
	}
	else if (m == HEAT1)
	{
		write_reg(HEATING2_RELAY,0x0000); // Heater 2 off
		write_reg(COOLING1_RELAY,0x0000); // Cooler 1 off
		write_reg(COOLING2_RELAY,0x0000); // Cooler 2 off
		write_reg(HEATING1_RELAY,0xffff); // Heater 1 on
	}
	else if (m == HEAT2)
	{
		write_reg(COOLING1_RELAY,0x0000); // Cooler 1 off
		write_reg(COOLING2_RELAY,0x0000); // Cooler 2 off
		write_reg(HEATING1_RELAY,0xffff); // Heater 1 on
		write_reg(HEATING2_RELAY,0xffff); // Heater 2 on
	}
	else
	{
		write_reg(HEATING1_RELAY,0x0000); // Heater 1 off
		write_reg(COOLING1_RELAY,0x0000); // Cooler 1 off
		write_reg(COOLING2_RELAY,0x0000); // Cooler 2 off
		write_reg(HEATING2_RELAY,0x0000); // Heater 2 off
	}
	// Actuate the fan
	if ((m == IDLE || m == UNKNOWN) && fan == 0)
		write_reg(FAN_RELAY,0x0000); // Fan off
	else
		write_reg(FAN_RELAY,0xffff); // Fan on
}

/**
 * API for the whole building
 */
static const int numTStats = 4;
static const int TStatAddrIndex[numTStats] = {1,2,3,4};
static Thermostat* tstats[numTStats] = {NULL,NULL,NULL,NULL};
static volatile double tempData[numTStats] = {25.0,25.0,25.0,25.0}; // Temperature readings
static volatile Thermostat::hvac_mode_t hvac_mode[numTStats] = {
	Thermostat::IDLE,
	Thermostat::IDLE,
	Thermostat::IDLE,
	Thermostat::IDLE
}; // Modes
static volatile double highLimit[numTStats] = {26.0,26.0,26.0,26.0}; // High temp limits
static volatile double lowLimit[numTStats] = {25.0,25.0,25.0,25.0}; // Low temp limits
static volatile double outdoorTemp = 25.0f;
static volatile bool doScan = true;
static pthread_t scan_thrd;

static void* scan(void*)
{
	const char* fileName[2] = {"scanA.csv","scanB.csv"};
	int lineCount = 0;
	int fileIndex = 0;
	int whichStat = 0;
	ofstream fout(fileName[fileIndex]);
	while (doScan)
	{
		while (Thermostat::bad())
		{
			try
			{
				Thermostat::reset();
			}
			catch(ModbusException error)
			{
			}
		}
		for (int k = 0; k < numTStats; k++)
		{
			int i = whichStat;
			whichStat = (whichStat+1)%numTStats;
			if (tstats[i] != NULL)
			{
				Thermostat::hvac_mode_t currentMode = Thermostat::UNKNOWN;
				try
				{
					// Set default values for registers
					tstats[i]->write_defaults();
					// Set the mode 
					tstats[i]->mode(hvac_mode[i]);
					// Get indoor temperature
					tempData[i] = tstats[i]->temp();
					// Get the temperature limits
					tstats[i]->temp_limits(highLimit[i],lowLimit[i]);
					// Get the actual mode for reporting
					currentMode = tstats[i]->mode(); 
				}
				catch(ModbusException error)
				{
				}
				if (Thermostat::bad())
				{
					fout << gettimestr() << ",no data," <<endl;
					break;
				}
				else
				{
					fout << gettimestr() << ",tstat_addr," << TStatAddrIndex[i];
					fout << ",temp," << tempData[i];
					fout << ",actual_mode," << Thermostat::mode_to_str(currentMode);
					fout << ",selected_mode," << Thermostat::mode_to_str(hvac_mode[i]);
					fout << ",low_temp_lim," << lowLimit[i];
					fout << ",high_temp_lim," << highLimit[i];
					fout << endl;
				}
			}
		}
		fout.flush();
		lineCount++;
		if (lineCount > 10000000) // A little over 1 year of data at 10 seconds
		{
			fout.close();
			lineCount = 0;
			fileIndex = (fileIndex+1)%2;
			fout.open(fileName[fileIndex]);
		}
		if (!Thermostat::bad())
			millisleep(10000);
	}
	fout.close();
	return NULL;
}

void init_building()
{
	for (int i = 0; i < numTStats; i++)
	{
		tstats[i] = new Thermostat(TStatAddrIndex[i]);
	}
	pthread_create(&scan_thrd,NULL,scan,NULL);
}

void free_building()
{
	doScan = false;
	pthread_join(scan_thrd,NULL);
	for (int i = 0; i < numTStats; i++)
		delete tstats[i];
}

int get_num_zones()
{
	return numTStats;
}

double get_high_temp_limit(int zone)
{
	return highLimit[zone];
}

double get_low_temp_limit(int zone)
{
	return lowLimit[zone];
}

double get_indoor_temp(int zone)
{
	return tempData[zone];
}

void set_deadbands(int zone, double cool, double heat)
{
	tstats[zone]->set_deadbands(cool,heat);
}

void set_fan_mode(int zone, int mode)
{
	tstats[zone]->set_fan_mode(mode);
}

double get_outdoor_temp()
{
	return outdoorTemp;
}

void set_hvac_mode(int zone, int mode)
{
	if (mode == 0)
		hvac_mode[zone] = Thermostat::IDLE;
	else if (mode == 1)
		hvac_mode[zone] = Thermostat::HEAT1;
	else if (mode == 2)
		hvac_mode[zone] = Thermostat::HEAT2;
	else if (mode == -1)
		hvac_mode[zone] = Thermostat::COOL1;
	else if (mode == -2)
		hvac_mode[zone] = Thermostat::COOL2;
	else assert(false);
}

void advance(double dt_Hrs)
{
}



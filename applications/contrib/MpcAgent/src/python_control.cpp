#include "building.h"
#include "MPC.h"

/**
 * This wraps a single instance of the control in a C-API that can be
 * called from python.
 */

extern "C"
{
	// Initialize the control structure to work with the
	// given number of zones.
	void init_control(int numZones);
	// Clean when done with the control
	void free_control();
	// Change the upper limit for a zone
	void set_upper_limit(int zone, double degsC);
	// Change the lower limit for a zone
	void set_lower_limit(int zone, double degsC);
	// Change the temperature data for a zone
	void set_zone_temp(int zone, double degsC);
	// Change the reading for the outside air temperature
	void set_outside_temp(double degsC);
	// Change the limit on the number of units to run
	void set_max_units(int units);
	// Run the control
	void run_control();
	// Get the command for the HVAC at a zone. 
	// -2 = cool2, -1 = cool1, 0 = idle, 1 = heat1, 2 = heat2
	int get_hvac_command(int zone);
	// Get the desired control period in seconds
	double get_control_period();
};

/**
 * Proxy for data received via the python calls or to be returned
 * via the python calls.
 */
class PythonBuildingProxy:
	public BuildingProxy
{
	public:
		PythonBuildingProxy(int numZones);
		/// Destructor
		virtual ~PythonBuildingProxy();
		/// Get the number of zones in the building
		virtual int getNumZones() { return numZones; }
		/// Switch an HVAC to its cooling mode
		virtual void setCool(int zone, int stage) { mode[zone] = -stage; }
		virtual int isCooling(int zone) { return ((mode[zone] < 0) ? -mode[zone] : 0); }
		/// Switch an HVAC to its heatinging mode
		virtual void setHeat(int zone, int stage) { mode[zone] = stage; }
		virtual int isHeating(int zone) { return ((mode[zone] > 0) ? mode[zone] : 0); }
		/// Switch an HVAC off
		virtual void setOff(int zone) { mode[zone] = 0; }
		virtual bool isOff(int zone) { return mode[zone] == 0; }
		/// Read the outdoor air temperature in degrees Celcius
		virtual double getOutdoorTemp() { return outdoorTemp; }
		/// Read the indoor air temperature in degrees Celcius
		virtual double getIndoorTemp(int zone) { return indoorTemp[zone]; }
		/// Read the thermostat upper limit in degrees Celcius
		virtual double getUpperLimit(int zone) { return upperLimit[zone]; }
		/// Read the thermostat lower limit in degrees Celcius
		virtual double getLowerLimit(int zone) { return lowerLimit[zone]; }
		/// Get the mode for a zone. 1=heat, -1=cool, 0=off
		int getMode(int zone) { return mode[zone]; }
		/// Set the current reading for the indoor air temperature
		void setIndoorTemp(int zone, double degsC) { indoorTemp[zone] = degsC; }
		/// Set the current reading for the outdoor air temperature
		void setOutdoorTemp(double degsC) { outdoorTemp = degsC; }
		/// Set the lower limit for indoor air temperature
		void setLowerLimit(int zone, double degsC) { lowerLimit[zone] = degsC; }
		/// Set the upper limit for indoor air temperature
		void setUpperLimit(int zone, double degsC) { upperLimit[zone] = degsC; }
	private:
		const int numZones;
		int* mode;
		double* indoorTemp;
		double* lowerLimit;
		double* upperLimit;
		double outdoorTemp;
};

PythonBuildingProxy::PythonBuildingProxy(int numZones):
	BuildingProxy(),
	numZones(numZones),
	mode(new int[numZones]),
	indoorTemp(new double[numZones]),
	lowerLimit(new double[numZones]),
	upperLimit(new double[numZones]),
	outdoorTemp(0.0)
{
	for (int i = 0; i < numZones; i++)
	{
		indoorTemp[i] = 0.0;
		lowerLimit[i] = -10.0;
		upperLimit[i] = 10.0;
		mode[i] = 0;
	}
}

PythonBuildingProxy::~PythonBuildingProxy()
{
	delete [] mode;
	delete [] indoorTemp;
	delete [] lowerLimit;
	delete [] upperLimit;
}

/**
 * Instances of the control and proxy.
 */
static PythonBuildingProxy* proxy = NULL;
static MPC* cntrl = NULL;

void init_control(int numZones)
{
	proxy = new PythonBuildingProxy(numZones);
	cntrl = new MPC(proxy);
}

void free_control()
{
	delete proxy;
	delete cntrl;
	proxy = NULL;
	cntrl = NULL;
}

void set_upper_limit(int zone, double degsC)
{
	proxy->setUpperLimit(zone,degsC);
}

void set_lower_limit(int zone, double degsC)
{
	proxy->setLowerLimit(zone,degsC);
}

void set_zone_temp(int zone, double degsC)
{
	proxy->setIndoorTemp(zone,degsC);
}

void set_outside_temp(double degsC)
{
	proxy->setOutdoorTemp(degsC);
}

void set_max_units(int units)
{
	cntrl->setMaxUnits(units);
}

void run_control()
{
	cntrl->periodExpired();
}

int get_hvac_command(int zone)
{
	return proxy->getMode(zone);
}

double get_control_period()
{
	return cntrl->getPeriodSeconds();
}


#ifndef _rbc_h_
#define _rbc_h_
#include "control.h"

/**
 * Rule based control of multiple HVAC and temperature sensors.
 */
class RBC:
	public Control
{
	public:
		RBC(BuildingProxy* bldg);
		/// Execute a periodic control action
		void periodExpired();
		/// What is the execution period?
		double getPeriodSeconds() { return period; }
		/// Destructor
		~RBC();
		std::string getState();
	protected:
		// Sampling period
		const double period;
		// Number of zones in the model
		const int numZones;
		// Maximum number of active units
		const int maxUnits;
		// Control deadband
		const double deadBand;
		// Current number of active units
		int activeUnits;
		// Cache for sensor data
		double *Tin, *Tref, Tout;
		enum HvacMode { COOL = -1 , IDLE = 0,  HEAT = 1 };
		// Command at last period
		HvacMode* hvacMode;
		// Periods for which command has been active
		unsigned int* elapsed;
};

#endif

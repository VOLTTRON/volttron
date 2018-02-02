#ifndef _simplecontrol_h_
#define _simplecontrol_h_
#include "control.h"

class SimpleControl:
	public Control
{
	public:
		SimpleControl(BuildingProxy* bldg);
		/// Execute a periodic control action
		void periodExpired();
		/// What is the execution period?
		double getPeriodSeconds();
		/// Destructor
		~SimpleControl();
		std::string getState();
	protected:
		double tRange;
		enum Mode { HEATING, COOLING, IDLE };
		Mode *mode;
};

#endif

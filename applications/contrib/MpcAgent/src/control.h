#ifndef _control_h_
#define _control_h_
#include "building.h"
#include <string>

/**
 * Abstract base class for all types of control
 * objects.
 */
class Control
{
	public:
		/// Create a control for a building
		Control(BuildingProxy* bldg):bldg(bldg){}
		/// Execute a periodic control action
		virtual void periodExpired() = 0;
		/// What is the execution period in seconds?
		virtual double getPeriodSeconds() = 0;
		/// Get a description of the control state
		virtual std::string getState() = 0;
		/// Destructor
		virtual ~Control(){}
	protected:
		BuildingProxy* bldg;
};

#endif

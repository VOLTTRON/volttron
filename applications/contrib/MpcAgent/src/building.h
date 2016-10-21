#ifndef _building_h_
#define _building_h_
#include <exception>
#include <list>
#include <string>

/**
 * Exception to indicate an unsupported 
 * method or an error in acquiring a property.
 */
class BuildingException:
	public std::exception
{
	public:
		BuildingException(std::string errMsg =
			"unknown problem with building property") throw()
			:errMsg(errMsg){}
		BuildingException(const BuildingException& other) throw()
			:errMsg(other.errMsg){}
		BuildingException& operator=(const BuildingException& other) throw() {
			errMsg = other.errMsg;
			return *this;
		}
		~BuildingException() throw(){}
		const char* what() const throw() {
			return errMsg.c_str();
		}
	private:
		std::string errMsg;
};

/**
 * Abstract class for access and control of
 * the building equipment.
 */
class BuildingProxy
{
	public:
		/// Constructor
		BuildingProxy(){}
		/**
		 * Get the number of zones in the building. A zone is
		 * a paring of a thermostat and an HVAC unit.
		 */
		virtual int getNumZones() = 0;
		/// Switch an HVAC to its cooling mode
		virtual void setCool(int zone, int stage = 1) = 0;
		virtual int isCooling(int zone) = 0;
		/// Switch an HVAC to its heating mode
		virtual void setHeat(int zone, int stage = 1) = 0;
		virtual int isHeating(int zone) = 0;
		/// Switch an HVAC off
		virtual void setOff(int zone) = 0;
		virtual bool isOff(int zone) = 0;
		/// Read the outdoor air temperature in degrees Celcius
		virtual double getOutdoorTemp() = 0;
		/// Read the indoor air temperature in degrees Celcius
		virtual double getIndoorTemp(int zone) = 0;
		/// Read the thermostat upper limit in degrees Celcius
		virtual double getUpperLimit(int zone) = 0;
		/// Read the thermostat lower limit in degrees Celcius
		virtual double getLowerLimit(int zone) = 0;
		/// Destructor
		virtual ~BuildingProxy(){}
};

#endif

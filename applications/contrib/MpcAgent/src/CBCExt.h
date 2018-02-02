#ifndef __CBCExt_h_
#define __CBCExt_h_
#include "adevs.h"
#include "simtest.h"

/**
 * Define the input and output type of the adevs models.
 */
#define OMC_ADEVS_IO_TYPE adevs::PortValue<BuildingEvent*>
#include "CBC.h"

/**
 * Test building based on CBC.mo
 */
class CBCExt:
    public CBC
{
	public:
		CBCExt();
		/// Destructor
		~CBCExt();
		double time_event_func(const double* q);
		void internal_event(double* q, const bool* state_event);
		void external_event(double* q, double e,
			const adevs::Bag<OMC_ADEVS_IO_TYPE>& xb);
		void confluent_event(double *q, const bool* state_event,
			const adevs::Bag<OMC_ADEVS_IO_TYPE>& xb);
		void output_func(const double *q, const bool* state_event,
			adevs::Bag<OMC_ADEVS_IO_TYPE>& yb);
		void gc_output(adevs::Bag<OMC_ADEVS_IO_TYPE>& gb);
     
    private:
		bool takeSample;
};

class CBCExtSolver:
	public adevs::Hybrid<OMC_ADEVS_IO_TYPE>,
	public BuildingModelInterface
{
	public:
		CBCExtSolver(CBCExt* model);
		~CBCExtSolver();
		std::string getState();
		static adevs::Devs<adevs::PortValue<BuildingEvent*> >* make();
	private:
		CBCExt* model;
};

class CBCExtProxy:
	public SimulatedBuildingProxy
{
	public:
		/// Constructor
		CBCExtProxy():
			SimulatedBuildingProxy()
		{
			for (int i = 0; i < 4; i++)
			{
				m_isHeating[i] = m_isCooling[i] = 0;
				outsideAirTemp = insideAirTemp[i] = 70.0;
				upperLimitTemp[i] = 70.0;
				lowerLimitTemp[i] = 65.0;
			}
		}
		/// Destructor
		~CBCExtProxy(){}
		void setOutdoorTemp(double degC) { outsideAirTemp = degC; }
		void setThermostatTemp(int zone, double degC) { insideAirTemp[zone] = degC; }
		void setThermostatUpperLimit(int zone, double degC) { upperLimitTemp[zone] = degC; }
		void setThermostatLowerLimit(int zone, double degC) { lowerLimitTemp[zone] = degC; }
		void setCool(int zone, int stage) {
			SimulatedBuildingProxy::activateCoolingUnit(zone,stage);
			SimulatedBuildingProxy::activateHeatingUnit(zone,0);
			m_isCooling[zone] = stage;
			m_isHeating[zone] = 0;
		}
		void setHeat(int zone, int stage) {
			SimulatedBuildingProxy::activateHeatingUnit(zone,stage);
			SimulatedBuildingProxy::activateCoolingUnit(zone,0);
			m_isHeating[zone] = stage;
			m_isCooling[zone] = 0;
		}
		void setOff(int zone) {
			SimulatedBuildingProxy::activateHeatingUnit(zone,0);
			SimulatedBuildingProxy::activateCoolingUnit(zone,0);
			m_isHeating[zone] = 0;
			m_isCooling[zone] = 0;
		}
		int getNumZones() { return 4; }
		int isCooling(int zone) { return m_isCooling[zone]; }
		int isHeating(int zone) { return m_isHeating[zone]; }
		bool isOff(int zone) { return !m_isHeating[zone] && !m_isCooling[zone]; }
		double getOutdoorTemp() { return outsideAirTemp; }
		double getIndoorTemp(int zone) { return insideAirTemp[zone]; }
		double getUpperLimit(int zone) { return upperLimitTemp[zone]; }
		double getLowerLimit(int zone) { return lowerLimitTemp[zone]; }
	private:
		double outsideAirTemp, insideAirTemp[4], upperLimitTemp[4], lowerLimitTemp[4];
		int m_isCooling[4], m_isHeating[4];
};

#endif


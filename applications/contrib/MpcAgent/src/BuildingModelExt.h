#ifndef __BuildingModelExt_h_
#define __BuildingModelExt_h_
#include "adevs.h"
#include "simtest.h"

/**
 * Define the input and output type of the adevs models.
 */
#define OMC_ADEVS_IO_TYPE adevs::PortValue<BuildingEvent*>
#include "BuildingModel.h"

/**
 * Test building based on BuildingModel.mo
 */
class BuildingModelExt:
    public BuildingModel
{
	public:
		BuildingModelExt();
		/// Destructor
		~BuildingModelExt();
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

class BuildingModelExtSolver:
	public adevs::Hybrid<OMC_ADEVS_IO_TYPE>,
	public BuildingModelInterface
{
	public:
		BuildingModelExtSolver(BuildingModelExt* model);
		~BuildingModelExtSolver();
		std::string getState();
		static BuildingModelExtSolver* make();
	private:
		BuildingModelExt* model;
};

class BuildingModelExtProxy:
	public SimulatedBuildingProxy
{
	public:
		/// Constructor
		BuildingModelExtProxy():
			SimulatedBuildingProxy(),
			outsideAirTemp(0.0f),
			insideAirTemp(0.0f),
			upperTemp(25.0f),
			lowerTemp(20.0f),
			m_isCooling(0),
			m_isHeating(0)
		{
		}
		/// Destructor
		~BuildingModelExtProxy(){}
		void setOutdoorTemp(double degC) { outsideAirTemp = degC; }
		void setThermostatTemp(int zone, double degC) { insideAirTemp = degC; }
		void setThermostatUpperLimit(int zone, double degC) { upperTemp = degC; }
		void setThermostatLowerLimit(int zone, double degC) { lowerTemp = degC; }
		void setCool(int zone, int stage) {
			SimulatedBuildingProxy::activateCoolingUnit(zone,stage);
			SimulatedBuildingProxy::activateHeatingUnit(zone,0);
			m_isCooling = stage;
			m_isHeating = 0;
		}
		void setHeat(int zone, int stage) {
			SimulatedBuildingProxy::activateHeatingUnit(zone,stage);
			SimulatedBuildingProxy::activateCoolingUnit(zone,0);
			m_isHeating = stage;
			m_isCooling = 0;
		}
		void setOff(int zone) {
			SimulatedBuildingProxy::activateHeatingUnit(zone,0);
			SimulatedBuildingProxy::activateCoolingUnit(zone,0);
			m_isHeating = 0;
			m_isCooling = 0;
		}
		int getNumZones() { return 1; }
		int isCooling(int zone) { return m_isCooling; }
		int isHeating(int zone) { return m_isHeating; }
		bool isOff(int zone) { return !m_isCooling && !m_isHeating; }
		double getOutdoorTemp() { return outsideAirTemp; }
		double getIndoorTemp(int zone) { return insideAirTemp; }
		double getUpperLimit(int zone) { return upperTemp; }
		double getLowerLimit(int zone) { return lowerTemp; }
	private:
		double outsideAirTemp, insideAirTemp, upperTemp, lowerTemp;
		int m_isCooling, m_isHeating;
};

#endif


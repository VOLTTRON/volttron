#ifndef __FourZoneBuildingExt_h_
#define __FourZoneBuildingExt_h_
#include "adevs.h"
#include "simtest.h"

/**
 * Define the input and output type of the adevs models.
 */
#define OMC_ADEVS_IO_TYPE adevs::PortValue<BuildingEvent*>
#include "FourZoneBuilding.h"

/**
 * Test building based on FourZoneBuilding.mo
 */
class FourZoneBuildingExt:
    public FourZoneBuilding
{
	public:
		FourZoneBuildingExt();
		/// Destructor
		~FourZoneBuildingExt();
		double time_event_func(const double* q);
		void internal_event(double* q, const bool* state_event);
		void external_event(double* q, double e,
			const adevs::Bag<OMC_ADEVS_IO_TYPE>& xb);
		void confluent_event(double *q, const bool* state_event,
			const adevs::Bag<OMC_ADEVS_IO_TYPE>& xb);
		void output_func(const double *q, const bool* state_event,
			adevs::Bag<OMC_ADEVS_IO_TYPE>& yb);
		void gc_output(adevs::Bag<OMC_ADEVS_IO_TYPE>& gb);
     
		static const int extraTempData;

    private:
		bool takeSample;
};

class MechanicalCoolingControl:
	public adevs::Atomic<adevs::PortValue<BuildingEvent*> >
{
	public:

		static const int tempData;
		static const int onOffCmd;

		MechanicalCoolingControl();
		void delta_int();
		void delta_ext(double e, const IO_Bag& xb);
		void delta_conf(const IO_Bag& xb);
		void output_func(IO_Bag& yb);
		void gc_output(IO_Bag& yb);
		double ta();
	private:
		const double setPoint, deadBand;
		bool off, change_mode;
};

class FourZoneBuildingExtSolver:
	public adevs::Hybrid<OMC_ADEVS_IO_TYPE>,
	public BuildingModelInterface
{
	public:
		FourZoneBuildingExtSolver(FourZoneBuildingExt* model);
		~FourZoneBuildingExtSolver();
		std::string getState();
		static adevs::Devs<adevs::PortValue<BuildingEvent*> >* make();
	private:
		FourZoneBuildingExt* model;
};

class FourZoneBuildingExtProxy:
	public SimulatedBuildingProxy
{
	public:
		/// Constructor
		FourZoneBuildingExtProxy():
			SimulatedBuildingProxy()
		{
			for (int i = 0; i < 4; i++)
			{
				m_isHeating[i] = m_isCooling[i] = 0;
				outsideAirTemp = insideAirTemp[i] = 22.0;
				upperLimitTemp[i] = 25.0;
				lowerLimitTemp[i] = 24.0;
			}
		}
		/// Destructor
		~FourZoneBuildingExtProxy(){}
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

class FourZoneBuildingWithExtraZone:
	public adevs::Digraph<BuildingEvent*>,
	public BuildingModelInterface
{
	public:
		FourZoneBuildingWithExtraZone():
			adevs::Digraph<BuildingEvent*>(),
			BuildingModelInterface()
		{
			MechanicalCoolingControl* cntrl = new MechanicalCoolingControl();
			FourZoneBuildingExt* bldg = new FourZoneBuildingExt();
			solver = new FourZoneBuildingExtSolver(bldg);
			SampleClock* clk = new SampleClock(1.0/60.0);
			add(solver);
			add(cntrl);
			add(clk);
			couple(this,BuildingModelInterface::sample,solver,BuildingModelInterface::sample);
			couple(solver,BuildingModelInterface::tempData,this,BuildingModelInterface::tempData);
			couple(this,BuildingModelInterface::onOffCmd,solver,BuildingModelInterface::onOffCmd);
			couple(clk,clk->sample,solver,BuildingModelInterface::sample);
		}

		std::string getState() { return solver->getState(); } 

	private:
		FourZoneBuildingExtSolver* solver;
};

#endif


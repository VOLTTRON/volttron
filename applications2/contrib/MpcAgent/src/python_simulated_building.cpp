#include "FourZoneBuildingExt.h"
#include "simtest.h"
#include "adevs.h"
#include "python_building_interface.h"
using namespace std;
using namespace adevs;

/**
 * Instance of the building.
 */
static FourZoneBuildingExt* bldg = NULL;
static FourZoneBuildingExtSolver* model = NULL;
static Simulator<PortValue<BuildingEvent*> >* sim = NULL;
static double tL = 0.0;

void init_building()
{
	tL = 0.0;
	bldg = new FourZoneBuildingExt();
	model = new FourZoneBuildingExtSolver(bldg);
	sim = new Simulator<PortValue<BuildingEvent*> >(model);
}

void free_building()
{
	delete sim;
	sim = NULL;
	delete bldg;
	bldg = NULL;
	model = NULL;
}

int get_num_zones()
{
	return 4;
}

double get_indoor_temp(int zone)
{
	if (zone == 0)
		return bldg->get_z1_t1();
	else if (zone == 1)
		return bldg->get_z2_t1();
	else if (zone == 2)
		return bldg->get_z3_t1();
	else // zone == 3
		return bldg->get_z4_t1();
}

double get_outdoor_temp()
{
	return bldg->get_outdoor_d1();
}

double get_high_temp_limit(int zone)
{
	return 25.0;
}

double get_low_temp_limit(int zone)
{
	return 20.0;
}

void set_hvac_mode(int zone, int mode)
{
	Bag<Event<PortValue<BuildingEvent*> > > xb;
	Event<PortValue<BuildingEvent*> > x;
	x.model = model;
	x.value.port = BuildingModelInterface::onOffCmd;
	if (mode == 0)
	{
		x.value.value = new OnOffEvent(HEATING_UNIT,zone,false);
		xb.insert(x);
		x.value.value = new OnOffEvent(COOLING_UNIT,zone,false);
		xb.insert(x);
	}
	else if (mode == 1)
	{
		x.value.value = new OnOffEvent(HEATING_UNIT,zone,true);
		xb.insert(x);
		x.value.value = new OnOffEvent(COOLING_UNIT,zone,false);
		xb.insert(x);
	}
	else // mode == -1
	{
		x.value.value = new OnOffEvent(HEATING_UNIT,zone,false);
		xb.insert(x);
		x.value.value = new OnOffEvent(COOLING_UNIT,zone,true);
		xb.insert(x);
	}
	sim->computeNextState(xb,tL);
	for (Bag<Event<PortValue<BuildingEvent*> > >::iterator iter = xb.begin();
			iter != xb.end(); iter++)
		delete (*iter).value.value;
}

void advance(double dt_Hrs)
{
	double tEnd = tL + dt_Hrs*3600.0;
	while (sim->nextEventTime() <= tEnd)
		sim->execNextEvent();
	Bag<Event<PortValue<BuildingEvent*> > > xb;
	Event<PortValue<BuildingEvent*> > x;
	x.model = model;
	x.value.port = BuildingModelInterface::sample;
	x.value.value = new BuildingEvent();
	xb.insert(x);
	sim->computeNextState(xb,tEnd);
	delete x.value.value;
	tL = tEnd;
	// Print current temperature
	cout << tL << " " << 
		get_indoor_temp(0) << " " <<
		get_indoor_temp(1) << " " << 
		get_indoor_temp(2) << " " << 
		get_indoor_temp(3) << " " <<
		get_outdoor_temp() << " ";
	cout << bldg->get_z1_heatStage() << ":" << bldg->get_z1_coolStage() << " ";
	cout << bldg->get_z2_heatStage() << ":" << bldg->get_z2_coolStage() << " ";
	cout << bldg->get_z3_heatStage() << ":" << bldg->get_z3_coolStage() << " ";
	cout << bldg->get_z4_heatStage() << ":" << bldg->get_z4_coolStage() << " ";
	cout << endl;
}

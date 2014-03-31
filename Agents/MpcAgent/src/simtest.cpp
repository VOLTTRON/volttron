#include "simtest.h"
#include <cstring>
using namespace adevs;
using namespace std;

// Building Proxy 
SimulatedBuildingProxy::SimulatedBuildingProxy():
	BuildingProxy(),
	pendingEvents()
{
}

SimulatedBuildingProxy::~SimulatedBuildingProxy()
{
	while (!pendingEvents.empty())
	{
		delete pendingEvents.front().value;
		pendingEvents.pop_front();
	}
}

void SimulatedBuildingProxy::activateCoolingUnit(int unit, int stage)
{
	PortValue<BuildingEvent*> pv;
	pv.port = ControlHarness::onOffCmd;
	pv.value = new OnOffEvent(COOLING_UNIT,unit,stage);
	pendingEvents.push_back(pv);
}

void SimulatedBuildingProxy::activateHeatingUnit(int unit, int stage)
{
	PortValue<BuildingEvent*> pv;
	pv.port = ControlHarness::onOffCmd;
	pv.value = new OnOffEvent(HEATING_UNIT,unit,stage);
	pendingEvents.push_back(pv);
}

void SimulatedBuildingProxy::getPendingEvents(IO_Bag& pending)
{
	list<PortValue<BuildingEvent*> >::iterator iter = pendingEvents.begin();
	for (; iter != pendingEvents.end(); iter++)
		pending.insert(*iter);
}

/// Control harness for testing the supervisory control algorithm

const int SampleClock::sample = 0;
const int ControlHarness::sample = 0;
const int ControlHarness::tempData = 1;
const int ControlHarness::onOffCmd = 2;

ControlHarness::ControlHarness(Control* control, SimulatedBuildingProxy* bldg):
	AtomicModel(),
	control(control),
	bldg(bldg),
	t_left(control->getPeriodSeconds()),
	run_control(false)
{
}

double ControlHarness::ta()
{
	if (bldg->hasPendingEvents() || run_control)
		return 0.0;
	else
		return t_left;
}

void ControlHarness::delta_int()
{
	if (bldg->hasPendingEvents())
	{
		bldg->clearPendingEvents();
	}
	else if (run_control)
	{
		control->periodExpired();
		run_control = false;
		t_left = control->getPeriodSeconds();
	}
	else
	{
		run_control = true;
	}
}

void ControlHarness::delta_ext(double e, const IO_Bag& xb)
{
	t_left -= e;
	IO_Bag::const_iterator iter = xb.begin();
	for (; iter != xb.end(); iter++)
	{
		assert((*iter).port == tempData);
		TemperatureEvent* temp =
			dynamic_cast<TemperatureEvent*>((*iter).value);
		if (temp->getItem() == THERMOSTAT_UPPER_SETPOINT)
			bldg->setThermostatUpperLimit(temp->getUnit(),temp->getTempC());
		else if (temp->getItem() == THERMOSTAT_LOWER_SETPOINT)
			bldg->setThermostatLowerLimit(temp->getUnit(),temp->getTempC());
		else if (temp->getItem() == THERMOSTAT_THERMOMETER)
			bldg->setThermostatTemp(temp->getUnit(),temp->getTempC());
		else if (temp->getItem() == OUTDOOR_THERMOMETER)
			bldg->setOutdoorTemp(temp->getTempC());
	}
}

void ControlHarness::delta_conf(const IO_Bag& xb)
{
	delta_int();
	delta_ext(0.0,xb);
}

void ControlHarness::output_func(IO_Bag& yb)
{
	if (bldg->hasPendingEvents())
		bldg->getPendingEvents(yb);
	else if (run_control != false)
	{
		adevs::PortValue<BuildingEvent*> pv;
		pv.port = sample;
		pv.value = new BuildingEvent();
		yb.insert(pv);
	}
}

// Interface for the Building system model

const int BuildingModelInterface::sample = 0;
const int BuildingModelInterface::tempData = 1;
const int BuildingModelInterface::onOffCmd = 2;

// Construct the complete model for control testing

TestModel::TestModel
	(
		Control* control,
		SimulatedBuildingProxy* bldgProxy,
		Devs<PortValue<BuildingEvent*> >* bldgModel
	):
	Digraph<BuildingEvent*>(),
	bldgProxy(bldgProxy),
	control(control),
	bldgModelOut("bldgm.dat"),
	bldgProxyOut("bldgp.dat"),
	cntrlOut("cntrl.dat")
{
	ControlHarness* cntrl = new ControlHarness(control,bldgProxy);
	add(cntrl);
	add(bldgModel);
	couple(cntrl,cntrl->sample,bldgModel,BuildingModelInterface::sample);
	couple(cntrl,cntrl->onOffCmd,bldgModel,BuildingModelInterface::onOffCmd);
	couple(bldgModel,BuildingModelInterface::tempData,cntrl,cntrl->tempData);
	bldgModelI = dynamic_cast<BuildingModelInterface*>(bldgModel);
}

void TestModel::print_state(double simTime)
{
	cntrlOut << simTime << " " << control->getState() << endl;
	bldgModelOut << simTime << " " << bldgModelI->getState() << endl;
	bldgProxyOut << simTime << " " << endl;
}

TestModel::~TestModel()
{
	cntrlOut.close();
	bldgModelOut.close();
	bldgProxyOut.close();
}



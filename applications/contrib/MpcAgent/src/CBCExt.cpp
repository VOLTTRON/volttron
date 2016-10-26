#include "CBCExt.h"
#include <sstream>
using namespace std;
using namespace adevs;

CBCExt::CBCExt():
	CBC(),
	takeSample(true)
{
}

CBCExt::~CBCExt()
{
}

double CBCExt::time_event_func(const double* q)
{
	double h = CBC::time_event_func(q);
	if (takeSample) h = 0.0;
	return h;
}

void CBCExt::internal_event(double* q, const bool* state_event)
{
	CBC::internal_event(q,state_event);
	takeSample = false;
}

void CBCExt::external_event(double* q, double e,
	const adevs::Bag<OMC_ADEVS_IO_TYPE>& xb)
{
	bool updateValues = false;
	CBC::external_event(q,e,xb);
	Bag<OMC_ADEVS_IO_TYPE>::const_iterator iter = xb.begin();
	for (; iter != xb.end(); iter++)
	{
		if ((*iter).port == BuildingModelInterface::sample) takeSample = true;
		else if ((*iter).port == BuildingModelInterface::onOffCmd)
		{
			OnOffEvent* cmd = dynamic_cast<OnOffEvent*>((*iter).value);
			if (cmd->getItem() == HEATING_UNIT)
			{
				updateValues = true;
				if (cmd->getUnit() == 0)
					set_z1_heatStage(cmd->getMode());
				else if (cmd->getUnit() == 1)
					set_z2_heatStage(cmd->getMode());
				else if (cmd->getUnit() == 2)
					set_z3_heatStage(cmd->getMode());
				else if (cmd->getUnit() == 3)
					set_z4_heatStage(cmd->getMode());
			}
			else if (cmd->getItem() == COOLING_UNIT)
			{
				updateValues = true;
				if (cmd->getUnit() == 0)
					set_z1_coolStage(cmd->getMode());
				else if (cmd->getUnit() == 1)
					set_z2_coolStage(cmd->getMode());
				else if (cmd->getUnit() == 2)
					set_z3_coolStage(cmd->getMode());
				else if (cmd->getUnit() == 3)
					set_z4_coolStage(cmd->getMode());
			}
		}
	}
	if (updateValues)
		update_vars(q,true);
}

void CBCExt::confluent_event(double *q, const bool* state_event,
	const adevs::Bag<OMC_ADEVS_IO_TYPE>& xb)
{
	internal_event(q,state_event);
	external_event(q,0.0,xb);
}

void CBCExt::output_func(const double *q, const bool* state_event,
	adevs::Bag<OMC_ADEVS_IO_TYPE>& yb)
{
	CBC::output_func(q,state_event,yb);
	update_vars(q,false);
	PortValue<BuildingEvent*> pv;
	pv.port = BuildingModelInterface::tempData;
	pv.value = new TemperatureEvent(OUTDOOR_THERMOMETER,0,get_outdoor_Tair());
	yb.insert(pv);
	pv.value = new TemperatureEvent(THERMOSTAT_THERMOMETER,0,get_z1_Troom());
	yb.insert(pv);
	pv.value = new TemperatureEvent(THERMOSTAT_THERMOMETER,1,get_z2_Troom());
	yb.insert(pv);
	pv.value = new TemperatureEvent(THERMOSTAT_THERMOMETER,2,get_z3_Troom());
	yb.insert(pv);
	pv.value = new TemperatureEvent(THERMOSTAT_THERMOMETER,3,get_z4_Troom());
	yb.insert(pv);
}

void CBCExt::gc_output(adevs::Bag<OMC_ADEVS_IO_TYPE>& gb)
{
	Bag<OMC_ADEVS_IO_TYPE>::iterator iter = gb.begin();
	for (; iter != gb.end(); iter++)
		delete ((*iter).value);
}
      
CBCExtSolver::CBCExtSolver(CBCExt* model):
	Hybrid<OMC_ADEVS_IO_TYPE>(
			model,
			new corrected_euler<OMC_ADEVS_IO_TYPE>(model,1E-4,0.1),
			new linear_event_locator<OMC_ADEVS_IO_TYPE>(model,1E-5)),
	BuildingModelInterface(),
	model(model)
{
}

CBCExtSolver::~CBCExtSolver()
{
}

string CBCExtSolver::getState()
{
	ostringstream sout;
	sout << model->get_z1_Troom() << " ";
	sout << model->get_z2_Troom() << " ";
	sout << model->get_z3_Troom() << " ";
	sout << model->get_z4_Troom() << " ";
	sout << model->get_outdoor_Tair() << " ";
	sout << model->get_z1_heatStage() << " " << model->get_z1_coolStage() << " ";
	sout << model->get_z2_heatStage() << " " << model->get_z2_coolStage() << " ";
	sout << model->get_z3_heatStage() << " " << model->get_z3_coolStage() << " ";
	sout << model->get_z4_heatStage() << " " << model->get_z4_coolStage() << " ";
	return sout.str();
}

Devs<PortValue<BuildingEvent*> >* CBCExtSolver::make()
{
	return new CBCExtSolver(new CBCExt());
}


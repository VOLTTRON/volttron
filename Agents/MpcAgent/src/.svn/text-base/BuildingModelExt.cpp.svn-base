#include "BuildingModelExt.h"
#include <sstream>
using namespace std;
using namespace adevs;

BuildingModelExt::BuildingModelExt():
	BuildingModel(),
	takeSample(true)
{
}

BuildingModelExt::~BuildingModelExt()
{
}

double BuildingModelExt::time_event_func(const double* q)
{
	double h = BuildingModel::time_event_func(q);
	if (takeSample) h = 0.0;
	return h;
}

void BuildingModelExt::internal_event(double* q, const bool* state_event)
{
	BuildingModel::internal_event(q,state_event);
	takeSample = false;
}

void BuildingModelExt::external_event(double* q, double e,
	const adevs::Bag<OMC_ADEVS_IO_TYPE>& xb)
{
	bool updateValues = false;
	BuildingModel::external_event(q,e,xb);
	Bag<OMC_ADEVS_IO_TYPE>::const_iterator iter = xb.begin();
	for (; iter != xb.end(); iter++)
	{
		if ((*iter).port == BuildingModelInterface::sample) takeSample = true;
		else if ((*iter).port == BuildingModelInterface::onOffCmd)
		{
			OnOffEvent* cmd = dynamic_cast<OnOffEvent*>((*iter).value);
			if (cmd->getItem() == HEATING_UNIT && get_heatStage() != cmd->getMode())
			{
				updateValues = true;
				set_heatStage(cmd->getMode());
			}
			else if (cmd->getItem() == COOLING_UNIT && get_coolStage() != cmd->getMode())
			{
				updateValues = true;
				set_coolStage(cmd->getMode());
			}
		}
	}
	if (updateValues)
		update_vars(q,true);
}

void BuildingModelExt::confluent_event(double *q, const bool* state_event,
	const adevs::Bag<OMC_ADEVS_IO_TYPE>& xb)
{
	internal_event(q,state_event);
	external_event(q,0.0,xb);
}

void BuildingModelExt::output_func(const double *q, const bool* state_event,
	adevs::Bag<OMC_ADEVS_IO_TYPE>& yb)
{
	BuildingModel::output_func(q,state_event,yb);
	update_vars(q,false);
	PortValue<BuildingEvent*> pv;
	pv.port = BuildingModelInterface::tempData;
	pv.value = new TemperatureEvent(OUTDOOR_THERMOMETER,0,get_d1());
	yb.insert(pv);
	pv.value = new TemperatureEvent(THERMOSTAT_THERMOMETER,0,get_t1());
	yb.insert(pv);
}

void BuildingModelExt::gc_output(adevs::Bag<OMC_ADEVS_IO_TYPE>& gb)
{
	Bag<OMC_ADEVS_IO_TYPE>::iterator iter = gb.begin();
	for (; iter != gb.end(); iter++)
		delete ((*iter).value);
}
      
BuildingModelExtSolver::BuildingModelExtSolver(BuildingModelExt* model):
	Hybrid<OMC_ADEVS_IO_TYPE>(
			model,
			new corrected_euler<OMC_ADEVS_IO_TYPE>(model,1E-5,0.1),
			new linear_event_locator<OMC_ADEVS_IO_TYPE>(model,1E-5)),
	BuildingModelInterface(),
	model(model)
{
}

BuildingModelExtSolver::~BuildingModelExtSolver()
{
}

string BuildingModelExtSolver::getState()
{
	ostringstream sout;
	sout << model->get_t1() << " " << model->get_d1() << " " 
		<< model->get_energyUsed();
	return sout.str();
}

BuildingModelExtSolver* BuildingModelExtSolver::make()
{
	BuildingModelExt* model = new BuildingModelExt();
	BuildingModelExtSolver* solver = new BuildingModelExtSolver(model);
	return solver;
}



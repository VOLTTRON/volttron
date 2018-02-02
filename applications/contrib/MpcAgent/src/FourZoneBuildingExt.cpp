#include "FourZoneBuildingExt.h"
#include <sstream>
using namespace std;
using namespace adevs;

const int FourZoneBuildingExt::extraTempData = 999999;

FourZoneBuildingExt::FourZoneBuildingExt():
	FourZoneBuilding(),
	takeSample(true)
{
}

FourZoneBuildingExt::~FourZoneBuildingExt()
{
}

double FourZoneBuildingExt::time_event_func(const double* q)
{
	double h = FourZoneBuilding::time_event_func(q);
	if (takeSample) h = 0.0;
	return h;
}

void FourZoneBuildingExt::internal_event(double* q, const bool* state_event)
{
	FourZoneBuilding::internal_event(q,state_event);
	takeSample = false;
}

void FourZoneBuildingExt::external_event(double* q, double e,
	const adevs::Bag<OMC_ADEVS_IO_TYPE>& xb)
{
	bool updateValues = false;
	FourZoneBuilding::external_event(q,e,xb);
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
				else if (cmd->getUnit() == 4)
					set_znoise_heatStage(cmd->getMode());
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
				else if (cmd->getUnit() == 4)
					set_znoise_coolStage(cmd->getMode());
			}
		}
	}
	if (updateValues)
		update_vars(q,true);
}

void FourZoneBuildingExt::confluent_event(double *q, const bool* state_event,
	const adevs::Bag<OMC_ADEVS_IO_TYPE>& xb)
{
	internal_event(q,state_event);
	external_event(q,0.0,xb);
}

void FourZoneBuildingExt::output_func(const double *q, const bool* state_event,
	adevs::Bag<OMC_ADEVS_IO_TYPE>& yb)
{
	FourZoneBuilding::output_func(q,state_event,yb);
	update_vars(q,false);
	PortValue<BuildingEvent*> pv;
	pv.port = BuildingModelInterface::tempData;
	pv.value = new TemperatureEvent(OUTDOOR_THERMOMETER,0,get_outdoor_d1());
	yb.insert(pv);
	pv.value = new TemperatureEvent(THERMOSTAT_THERMOMETER,0,get_z1_t1());
	yb.insert(pv);
	pv.value = new TemperatureEvent(THERMOSTAT_THERMOMETER,1,get_z2_t1());
	yb.insert(pv);
	pv.value = new TemperatureEvent(THERMOSTAT_THERMOMETER,2,get_z3_t1());
	yb.insert(pv);
	pv.value = new TemperatureEvent(THERMOSTAT_THERMOMETER,3,get_z4_t1());
	yb.insert(pv);
	pv.port = extraTempData;
	pv.value = new TemperatureEvent(THERMOSTAT_THERMOMETER,4,get_znoise_t1());
	yb.insert(pv);
}

void FourZoneBuildingExt::gc_output(adevs::Bag<OMC_ADEVS_IO_TYPE>& gb)
{
	Bag<OMC_ADEVS_IO_TYPE>::iterator iter = gb.begin();
	for (; iter != gb.end(); iter++)
		delete ((*iter).value);
}
      
FourZoneBuildingExtSolver::FourZoneBuildingExtSolver(FourZoneBuildingExt* model):
	Hybrid<OMC_ADEVS_IO_TYPE>(
			model,
			new corrected_euler<OMC_ADEVS_IO_TYPE>(model,1E-4,0.1),
			new linear_event_locator<OMC_ADEVS_IO_TYPE>(model,1E-5)),
	BuildingModelInterface(),
	model(model)
{
}

FourZoneBuildingExtSolver::~FourZoneBuildingExtSolver()
{
}

string FourZoneBuildingExtSolver::getState()
{
	ostringstream sout;
	double energyUsed = 0.0;
	energyUsed += model->get_z1_energyUsed();
	energyUsed += model->get_z2_energyUsed();
	energyUsed += model->get_z3_energyUsed();
	energyUsed += model->get_z4_energyUsed();
	sout << model->get_z1_t1() << " ";
	sout << model->get_z2_t1() << " ";
	sout << model->get_z3_t1() << " ";
	sout << model->get_z4_t1() << " ";
	sout << model->get_znoise_t1() << " ";
	sout << model->get_outdoor_d1() << " " << energyUsed << " ";
	sout << model->get_z1_heatStage() << " " << model->get_z1_coolStage() << " ";
	sout << model->get_z2_heatStage() << " " << model->get_z2_coolStage() << " ";
	sout << model->get_z3_heatStage() << " " << model->get_z3_coolStage() << " ";
	sout << model->get_z4_heatStage() << " " << model->get_z4_coolStage() << " ";
	sout << model->get_znoise_heatStage() << " " << model->get_znoise_coolStage() << " ";
	return sout.str();
}

Devs<PortValue<BuildingEvent*> >* FourZoneBuildingExtSolver::make()
{
	return new FourZoneBuildingWithExtraZone();
}

const int MechanicalCoolingControl::tempData = 0;
const int MechanicalCoolingControl::onOffCmd = 1;

MechanicalCoolingControl::MechanicalCoolingControl():
	Atomic<adevs::PortValue<BuildingEvent*> >(),
	setPoint(25.0),
	deadBand(1.0),
	off(true),
	change_mode(false)
{
}

double MechanicalCoolingControl::ta()
{
	if (change_mode) return 0.0;
	else return adevs_inf<double>();
}

void MechanicalCoolingControl::delta_int()
{
	off = !off;
}

void MechanicalCoolingControl::delta_ext(double e, const IO_Bag& xb)
{
	IO_Bag::const_iterator iter = xb.begin();
	for (; iter != xb.end(); iter++)
	{
		assert((*iter).port == tempData);
		TemperatureEvent* temp =
			dynamic_cast<TemperatureEvent*>((*iter).value);
		if (temp->getItem() == THERMOSTAT_THERMOMETER && temp->getUnit() == 4)
		{
			if (off && temp->getTempC() > setPoint)
				change_mode = true;
			else if (!off && temp->getTempC() < setPoint-deadBand)
				change_mode = true;
		}
	}
}

void MechanicalCoolingControl::delta_conf(const IO_Bag& xb)
{
	delta_int();
	delta_ext(0.0,xb);
}

void MechanicalCoolingControl::output_func(IO_Bag& yb)
{
	PortValue<BuildingEvent*> pv;
	pv.port = onOffCmd;
	pv.value = new OnOffEvent(COOLING_UNIT,4,1);
	yb.insert(pv);
}

void MechanicalCoolingControl::gc_output(IO_Bag& yb)
{
	IO_Bag::iterator iter = yb.begin();
	for (; iter != yb.end(); iter++)
		delete (*iter).value;
}


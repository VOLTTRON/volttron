#include "simtest.h"
#include "SimpleControl.h"
#include "MPC.h"
#include "BuildingModelExt.h"
#include "FourZoneBuildingExt.h"
#include "CBCExt.h"
#include <cstring>
using namespace adevs;
using namespace std;

static const double DAYS_TO_SECS = 60.0*60.0*24.0;
double tLastRecord = 0.0;
double tEnd = 15*DAYS_TO_SECS;
int lastPercentReport = 0;

// Main routine for simulation based testing
int main(int argc, char** argv)
{
	// Make the building
	Devs<PortValue<BuildingEvent*> >* model = NULL;
	SimulatedBuildingProxy* proxy = NULL;
	// model = BuildingModelExtSolver::make(); proxy = new BuildingModelExtProxy();
	// model = FourZoneBuildingExtSolver::make(); proxy = new FourZoneBuildingExtProxy();
	model = CBCExtSolver::make(); proxy = new CBCExtProxy();
	// Make the control
	Control* control =
		new MPC(proxy);
		// new SimpleControl(proxy);
	// Build the test model
	TestModel* testModel = new TestModel(control,proxy,model);
	// Simulate the model
	Simulator<PortValue<BuildingEvent*> >* sim =
		new Simulator<PortValue<BuildingEvent*> >(testModel);
	while (sim->nextEventTime() < tEnd)
	{
		double tL = sim->nextEventTime();
		sim->execNextEvent();
		if (tL - tLastRecord > 30.0)
		{
			tLastRecord = tL;
			testModel->print_state(tL);
		}
		int percentDone = ((tL/tEnd)*100.0);
		if (percentDone > lastPercentReport)
		{
			lastPercentReport = percentDone;
			cout << "\r" << percentDone << "\%\t";
			cout.flush();
		}
	}
	cout << endl << "done" << endl;
	delete sim;
	delete testModel;
	return 0;
}


#include "RBC.h"
#include "adevs.h"
#include <iostream>
#include <cassert>
#include <cmath>
#include <sstream>
using namespace std;
using namespace adevs;

RBC::RBC(BuildingProxy* bldg):
	Control(bldg),
	period(60.0),
	numZones(bldg->getNumZones()),
	maxUnits(2),
	deadBand(5.0),
	activeUnits(0)
{
	Tin = new double[numZones];
	Tref = new double[numZones];
	hvacMode = new HvacMode[numZones];
	elapsed = new unsigned int[numZones];
	for (int i = 0; i < numZones; i++)
	{
		elapsed[i] = 30;
		hvacMode[i] = IDLE;
	}
}

RBC::~RBC()
{
	delete [] Tin;
	delete [] Tref;
	delete [] hvacMode;
	delete [] elapsed;
}

void RBC::periodExpired()
{
	// Get sensor data from HVAC and update
	// elapsed time for units
	for (int i = 0; i < numZones; i++)
	{
		Tin[i] = bldg->getIndoorTemp(i);
		Tref[i] = bldg->getSetPoint(i);
		elapsed[i]++;
	}
	// Get outdoor temperature data
	Tout = bldg->getOutdoorTemp();
	// Deactive units
	for (int i = 0; i < numZones; i++)
	{
		if (((hvacMode[i] == COOL && Tin[i] < Tref[i]+deadBand)
			|| (hvacMode[i] == HEAT && Tin[i] > Tref[i]-deadBand))
				&& elapsed[i] >= 30)
		{
			hvacMode[i] = IDLE;
			bldg->setOff(i);
			elapsed[i] = 0;
			activeUnits--;
		}
	}
	// Activate units
	while (activeUnits < maxUnits)
	{
		// Find the inactive unit that is most out of
		// bounds
		double Omax = 0.0;
		int zoneMax = -1;
		for (int i = 0; i < numZones; i++)
		{
			double O = fabs(Tin[i]-Tref[i])-deadBand;
			if (hvacMode[i] == IDLE && O > Omax && elapsed[i] >= 30)
			{
				Omax = O;
				zoneMax = i;
			}
		}
		// Nothing to do
		if (zoneMax == -1) break;
		// Active the unit
		if (Tin[zoneMax] < Tref[zoneMax]-deadBand)
		{
			hvacMode[zoneMax] = HEAT;
			bldg->setHeat(zoneMax);
		}
		else
		{
			hvacMode[zoneMax] = COOL;
			bldg->setCool(zoneMax);
		}
		elapsed[zoneMax] = 0;
		activeUnits++;
	}
	assert(activeUnits <= maxUnits);
}

std::string RBC::getState()
{
	ostringstream strm;
	strm << endl;
	strm << "hvac=";
	int count = 0;	
	for (int i = 0; i < numZones; i++)
	{
		count += (hvacMode[i] != IDLE);
		strm << " " << hvacMode[i];
	}
	strm << endl;
	strm << "count=" << count;
	return strm.str();
}


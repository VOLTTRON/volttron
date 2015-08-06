#include "SimpleControl.h"
#include <iostream>
#include <cassert>
#include <sstream>
using namespace std;

SimpleControl::SimpleControl(BuildingProxy* bldg):
	Control(bldg),
	mode(new Mode[bldg->getNumZones()])
{
	for (int i = 0; i < bldg->getNumZones(); i++)
		mode[i] = IDLE;
}

void SimpleControl::periodExpired()
{
	for (int i = 0; i < bldg->getNumZones(); i++)
	{
		double tLower = bldg->getLowerLimit(i);
		double tUpper = bldg->getUpperLimit(i);
		double tInside = bldg->getIndoorTemp(i);
		// Cool the building
		if (tInside > tUpper) 
		{
			mode[i] = COOLING;
			bldg->setCool(i);
		}
		// Heat the building
		else if (tInside < tLower) 
		{
			mode[i] = HEATING;
			bldg->setHeat(i);
		}
		else
		{
			mode[i] = IDLE;
			bldg->setOff(i);
		}
	}
}

double SimpleControl::getPeriodSeconds()
{
	return 30.0*60.0;
}

std::string SimpleControl::getState()
{
	ostringstream strm;
	int count = 0;
	for (int i = 0; i < bldg->getNumZones(); i++)
	{
		if (mode[i] == HEATING) { count++; strm << "1 "; }
		else if (mode[i] == COOLING) { count++; strm << "-1 "; }
		else strm << "0 ";
	}
	strm << " " << count;
	return strm.str();
}

SimpleControl::~SimpleControl()
{
	delete [] mode;
}


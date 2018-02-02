#include "MPC.h"
#include <iostream>
#include <cassert>
#include <cmath>
#include <sstream>
#include <climits>
#include <cfloat>
#include <cstdlib>
using namespace std;

// From lapack

extern "C"
{
int dgelsd_(int *m, int *n, int *nrhs, 
	double *a, int *lda, double *b, int *ldb, double *s,
	double *rcond, int *rank, double *work, int *lwork,
	int *iwork, int *info);
};

double MPC::calc_dT( 
	const double*  Tinside,
	double Toutside,
	int zone,
	HvacMode mode
	)
{
	int k = 0, j;
	double dT = d[zone];
	if (mode == COOL1)
		dT += bc1[zone];
	else if (mode == COOL2)
		dT += bc2[zone];
	else if (mode == HEAT1)
		dT += bh1[zone];
	else if (mode == HEAT2)
		dT += bh2[zone];
	for (j = 0; j < numZones; j++)
	{
		if (j != zone)
		{
			dT += a[zone][k]*(Tinside[zone]-Tinside[j]);
			k++;
		}
	}
	dT += a[zone][k]*(Tinside[zone]-Toutside);
	return dT;
}

MPC::MPC(BuildingProxy* bldg):
	Control(bldg),
	period(10.0*60.0),
	numZones(bldg->getNumZones()),
	maxUnits(::max(numZones/2,1)),
	histSize(0),
	WORK_SIZE(10000000)
{
	dgelsd_WORK = new double[WORK_SIZE];
	dgelsd_IWORK = new int[WORK_SIZE];
	Tin = new double[numZones];
	Tupper = new double[numZones];
	Tlower = new double[numZones];
	TinHist = new list<double>[numZones];
	heatOnHist = new list<double>[numZones];
	coolOnHist = new list<double>[numZones];
	hvacMode = new HvacMode[numZones];
	for (int i = 0; i < numZones; i++)
		hvacMode[i] = IDLE;
	hvacTraj = new HvacMode[numZones];
	// Matrices for the model parameters
	a = new double*[numZones];
	d = new double[numZones];
	// Stage 1 cooling data
	bc1 = new double[numZones];
	// Stage 2 cooling data
	bc2 = new double[numZones];
	// Stage 1 heating data
	bh1 = new double[numZones];
	// Stage 2 heating data
	bh2 = new double[numZones];
	Terror = new double[numZones];
	for (int i = 0; i < numZones; i++)
	{
		Terror[i] = 0.0;
		bh1[i] = 1.0;
		bc1[i] = -1.0;
		bh2[i] = 2.0;
		bc2[i] = -2.0;
		d[i] = 0.0;
		a[i] = new double[numZones];
		for (int j = 0; j < numZones; j++)
		   a[i][j] = 0.0;	
	}
	// Make sure history data is sufficient to solve least squares problem
	Acols = maxHistSize = numZones+1;
	Arows = maxHistSize;
	// Matrices for LAPACK.
	A = new double[Arows*Acols];
	B = new double[Arows*numZones];
	S = new double[min(Arows,Acols)];
}

MPC::~MPC()
{
	delete [] Terror;
	delete [] d;
	delete [] dgelsd_WORK;
	delete [] dgelsd_IWORK;
	delete [] Tin;
	delete [] Tupper;
	delete [] Tlower;
	delete [] TinHist;
	delete [] heatOnHist;
	delete [] coolOnHist;
	delete [] hvacMode;
	delete [] hvacTraj;
	delete [] bc1;
	delete [] bh1;
	delete [] bc2;
	delete [] bh2;
	for (int i = 0; i < numZones; i++)
		delete [] a[i];
	delete [] a;
	delete [] A;
	delete [] B;
	delete [] S;
}

void MPC::trial(double& Q, double& O, HvacMode* trial_option)
{
	double dTout = Tout-ToutHist.back();
	O = Q = 0.0;
	for (int i = 0; i < numZones; i++)
	{
		double Qcost = 0.0;
		if (trial_option[i] == HEAT1 || trial_option[i] == COOL1) Qcost = 1.0;
		else if (trial_option[i] == HEAT2 || trial_option[i] == COOL2) Qcost = 2.0;
		Q += Qcost;
		double T = Tin[i] + calc_dT(Tin,Tout+dTout,i,trial_option[i]);
		double diffAbove = T-Tupper[i];
		double diffBelow = Tlower[i]-T;
		double maxDiff = (diffAbove > diffBelow) ? diffAbove : diffBelow;
		if (maxDiff > 0.0) O += maxDiff;
	}
}

void MPC::build_model()
{
	bool heatOrCool = false;
	for (int j = 0; j < numZones; j++)
	{
		list<double>::iterator iter;
		for (iter = heatOnHist[j].begin(); iter != heatOnHist[j].end(); iter++)
			if ((*iter) != 0.0) heatOrCool = true;
		for (iter = coolOnHist[j].begin(); iter != coolOnHist[j].end(); iter++)
			if ((*iter) != 0.0) heatOrCool = true;
	}
	for (int zone = 0; zone < numZones; zone++)
	{
		if (heatOrCool)
		{
			build_hvac_model(zone);
		}
		else
		{
			build_thermo_model(zone,a[zone]);
		}
	}
}

void MPC::build_hvac_model(int zone)
{
	double T[numZones];
	if (hvacMode[zone] == IDLE) return; // Nothing to do
	// Get the most recently recorded temperature for each zone
	for (int i = 0; i < numZones; i++)
		T[i] = TinHist[i].back();
	// Expected temperature without the HVAC
	double TnoHvac = T[zone] + calc_dT(T,ToutHist.back(),zone,IDLE);
	double cc = Tin[zone] - TnoHvac;
	// Weighting term based on the forecast error. New estimate
	// will depend on current estimate, previous estimate, and
	// a weighting of these for the forecast error. If the error
	// is large, keep the previous estimate. If the error
	// is small, keep the new estimate.
	double alpha = min(1.0,fabs(Terror[zone]));
	// Get the new estimate
	// If the temperature fell, assume it is due to cooling
	if (cc < 0.0)
	{

		if (hvacMode[zone] == COOL1)
		{
			bc1[zone] = alpha*bc1[zone]+(1.0-alpha)*cc;
		}
		else if (hvacMode[zone] == COOL2)
		{
			bc2[zone] = alpha*bc2[zone]+(1.0-alpha)*cc;
		}
	}
	// If the temperature rose, assume it is due to heating
	else if (cc > 0.0)
	{
		if (hvacMode[zone] == HEAT1)
		{
			bh1[zone] = alpha*bh1[zone]+(1.0-alpha)*cc;
		}
		else if (hvacMode[zone] == HEAT2)
		{
			bh2[zone] = alpha*bh2[zone]+(1.0-alpha)*cc;
		}
	}
}

void MPC::build_thermo_model(int zone, double* alpha)
{
	// Fill in the A matrix
	list<double>::iterator iter1, iter2;
	int i = 0;
	for (int j = 0; j < numZones; j++)
	{
		if (j != zone)
		{
			iter1 = TinHist[zone].begin();
			iter2 = TinHist[j].begin();
			for (; iter1 != TinHist[zone].end(); iter1++, iter2++)
				A[i++] = (*(iter1))-(*(iter2));
		}
	}
	iter1 = TinHist[zone].begin();
	iter2 = ToutHist.begin();
	for (; iter1 != TinHist[zone].end(); iter1++, iter2++)
		A[i++] = (*(iter1))-(*(iter2));
	for (int j = 0; j < Arows; j++)
		A[i++] = 1.0;
	// Fill in the B matrix
	i = 0;
	iter1 = TinHist[zone].begin();
	iter2 = TinHist[zone].begin();
	for (; iter1 != TinHist[zone].end(); iter1++)
	{
		iter2++;
		if (iter2 != TinHist[zone].end())
			B[i++] = (*(iter2))-(*(iter1));
		else
			break;
	} 
	B[i++] = Tin[zone]-(*iter1);
	// Solve the least squares problem over the available data
	int LDB = max(Arows,Acols);
	double RCOND = 0.01;
	int NRHS = numZones;
	int info, RANK;
	dgelsd_(
		&Arows,
		&Acols,
		&NRHS,
		A,
		&Arows,
		B,
		&LDB,
		S,
		&RCOND,
		&RANK,
		dgelsd_WORK,
		&WORK_SIZE,
		dgelsd_IWORK,
		&info);  
	// Pick out the model parameters if the solution was found.
	if (info == 0)
	{
		i = 0;
		for (int j = 0; j < numZones; j++)
		{
			alpha[j] = B[i++];
		}
		d[zone] = B[i++];
	}
}

void MPC::periodExpired()
{
	// Generate forecast for calculating model error
	if (histSize >= maxHistSize)
	{
		double dTout = Tout-ToutHist.back();
		for (int i = 0; i < numZones; i++)
			Terror[i] = Tin[i] + calc_dT(Tin,Tout+dTout,i,hvacTraj[i]);
	}
	// Get sensor data from HVAC
	for (int i = 0; i < numZones; i++)
	{
		Tin[i] = bldg->getIndoorTemp(i);
		Tupper[i] = bldg->getUpperLimit(i);
		Tlower[i] = bldg->getLowerLimit(i);
	}
	// Get outdoor temperature data
	Tout = bldg->getOutdoorTemp();
	// Build the model and take a control action
	// if there is sufficient data to make a
	// decision.
	if (histSize >= maxHistSize)
	{
		for (int i = 0; i < numZones; i++)
			Terror[i] -= Tin[i];
		build_model();
		select_control();
	}
	// Store historic data
	store_data();
	// Print the state
	cout << getState() << endl;
}

void MPC::store_data()
{
	// Get data and append it to the history 
	histSize++;
	for (int i = 0; i < numZones; i++)
	{
		TinHist[i].push_back(Tin[i]);
		if (histSize > maxHistSize)
			TinHist[i].pop_front();
		heatOnHist[i].push_back(bldg->isHeating(i));
		if (histSize > maxHistSize)
			heatOnHist[i].pop_front();
		coolOnHist[i].push_back(bldg->isCooling(i));
		if (histSize > maxHistSize)
			coolOnHist[i].pop_front();
	}
	ToutHist.push_back(Tout);
	if (histSize > maxHistSize)
		ToutHist.pop_front();
	if (histSize > maxHistSize)
		histSize--;
}

bool MPC::is_legitimate_option(HvacMode* trial_option)
{
	int inService = 0;
	for (int i = 0; i < numZones; i++)
	{
		inService += (trial_option[i] != IDLE);
		// cooling -> too hot (i.e., !cooling or too hot)
		bool coolRule = (!(trial_option[i] == COOL1 || trial_option[i] == COOL2)) || (Tin[i] > Tupper[i]);
		// heating -> too cold (i.e., !heating or too cold)
		bool heatRule = (!(trial_option[i] == HEAT1 || trial_option[i] == HEAT2)) || (Tin[i] < Tlower[i]);
		if (!coolRule || !heatRule) return false;
	}
	bool countOk = inService <= maxUnits;
	return (countOk);
}

void MPC::select_control(HvacMode* trial_option)
{
	static int zone = 0;
	static double Qmin = DBL_MAX, Omin = DBL_MAX;
	// Start of the search
	if (trial_option == NULL)
	{
		assert(zone == 0);
		Qmin = DBL_MAX;
		Omin = DBL_MAX;
		trial_option = new HvacMode[numZones];
	}
	// Build a trial option by depth-first traversal of the option tree
	if (zone < numZones)
	{
		// Explore idle branch for this zone
		trial_option[zone] = IDLE;
		zone++;
		select_control(trial_option);
		zone--;
		// Repeat for HEAT1
		trial_option[zone] = HEAT1;
		zone++;
		select_control(trial_option);
		zone--;
		// Repeat for HEAT2
		trial_option[zone] = HEAT2;
		zone++;
		select_control(trial_option);
		zone--;
		// Repeat for COOL1
		trial_option[zone] = COOL1;
		zone++;
		select_control(trial_option);
		zone--;
		// Repeat for COOL2
		trial_option[zone] = COOL2;
		zone++;
		select_control(trial_option);
		zone--;
	}
	// At leaf node of the tree, score each option and keep the best one
	else if (is_legitimate_option(trial_option))
	{
		// Get the score for this option
		double Q, O;
		trial(Q,O,trial_option);
		// If it is a better option then go with it
		if (O < Omin || (O == Omin && Q < Qmin))
		{
			Omin = O;
			Qmin = Q;
			for (int k = 0; k < numZones; k++)
			{
				hvacMode[k] = trial_option[k];
			}
		}
	}
	// Done with the search, so apply control and cleanup
	if (zone == 0)
	{
		for (int k = 0; k < numZones; k++)
		{
			if (hvacMode[k] == IDLE)
				bldg->setOff(k);
			else if (hvacMode[k] == COOL1)
				bldg->setCool(k,1);
			else if (hvacMode[k] == COOL2)
				bldg->setCool(k,2);
			else if (hvacMode[k] == HEAT1)
				bldg->setHeat(k,1);
			else if (hvacMode[k] == HEAT2)
				bldg->setHeat(k,2);
		}
		delete [] trial_option;
	}
}

static void print_vector(ostream& strm, double* V, int els)
{
	for (int i = 0; i < els; i++)
		strm << V[i] << " ";
	strm << endl;
}

static void print_matrix(ostream& strm, double** M, int rows, int cols)
{
	for (int i = 0; i < rows; i++)
	{
		for (int j = 0; j < cols; j++)
			strm << M[i][j] << " ";
		strm << endl;
	}
}

std::string MPC::getState()
{
	ostringstream strm;
	strm << endl;
	if (histSize >= maxHistSize)
	{
		strm << "a=" << endl;
		print_matrix(strm,a,numZones,numZones);
		strm << "bc1= ";
		print_vector(strm,bc1,numZones);
		strm << "bh1= ";
		print_vector(strm,bh1,numZones);
		strm << "bc2= ";
		print_vector(strm,bc2,numZones);
		strm << "bh2= ";
		print_vector(strm,bh2,numZones);
		strm << "d= ";
		print_vector(strm,d,numZones);
		strm << "error= ";
		print_vector(strm,Terror,numZones);
	}
	else
		strm << "Collecting data: " << histSize << " / " << maxHistSize << endl;
	strm << "hvac=";
	int count = 0;	
	for (int i = 0; i < numZones; i++)
	{
		count += (hvacMode[i] != IDLE);
		strm << " " << hvacMode[i];
	}
	assert(count <= maxUnits);
	strm << endl;
	strm << "count = " << count;
	return strm.str();
}


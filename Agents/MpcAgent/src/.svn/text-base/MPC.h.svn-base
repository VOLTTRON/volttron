#ifndef _mpc_h_
#define _mpc_h_
#include "control.h"

/**
 * Model predicative control for multiple HVAC and temperature sensors.
 */
class MPC:
	public Control
{
	public:
		MPC(BuildingProxy* bldg);
		/// Execute a periodic control action
		void periodExpired();
		/// What is the execution period?
		double getPeriodSeconds() { return period; }
		/// Set the maximum number of units to run
		void setMaxUnits(int maxUnits) { this->maxUnits = maxUnits; }
		/// Destructor
		~MPC();
		std::string getState();
	private:
		// Sampling period
		const double period;
		// Number of zones in the model
		const int numZones;
		// Maximum number of HVAC units to run
		int maxUnits;
		// Model parameters matrices. 
		double **a; // Thermodynamic state transition matrix
		double *d; // Heat input from misc. sources
		double *bc1; // Stage 1 cooling data
		double *bh1; // Stage 1 heating data
		double *bc2; // Stage 2 cooling data
		double *bh2; // Stage 2 heating data
		// Error data for forecast
		double* Terror;
		// Cache for sensor data 
		double *Tin, *Tupper, *Tlower, Tout;
		// History of sensor data
		std::list<double> *TinHist, *heatOnHist, *coolOnHist, ToutHist;
		// Size of data history
		int histSize;
		// Maximum size of the data history
		int maxHistSize;
		enum HvacMode
		{
			COOL2 = -2, // Stage 2
			COOL1 = -1, // Stage 1
			IDLE = 0, // Off
			HEAT1 = 1, // Stage 1
			HEAT2 = 2 // Stage 2
		};
		// Command at last period
		HvacMode* hvacMode;
		// Trial command
		HvacMode* hvacTraj;

		bool is_legitimate_option(HvacMode* trial_option);
		void store_data();
		void build_model();
		void build_hvac_model(int zone);
		// Returns true on success, false on failure
		void build_thermo_model(int zone, double* alpha);
		void select_control(HvacMode* trial_option = NULL);
		void trial(double& Q, double& O, HvacMode* trial_option);
		double calc_dT(const double* Tinside, double Toutside,
				int zone, HvacMode mode);
		// Data for LAPACK
		int Arows, Acols;
		double* A;
		double* B;
		double* S;
		int WORK_SIZE;
		double* dgelsd_WORK;
		int* dgelsd_IWORK;
};

#endif

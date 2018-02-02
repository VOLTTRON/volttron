#include "BuildingModel.h"
#include "adevs_modelica_runtime.h"
using namespace adevs;

// This is used by the residual functions
static BuildingModel* active_model;


void BuildingModel::bound_params()
{
}

BuildingModel::BuildingModel(
    int extra_state_events, double eventHys):
    ode_system<OMC_ADEVS_IO_TYPE>(
        4+1, // Number of state variables plus one for the clock
        2+2*1+extra_state_events // Number of state event functions
    ),
    epsilon(eventHys),
    zc(NULL),
    samples(NULL),
    delays(NULL),
    eventFuncs(NULL)
 {
     timeValue = 0.0;
     if (numRelations() > 0)
         zc = new int[numRelations()];
     if (numTimeEvents() > 0)
     {
         samples = new AdevsSampleData*[numTimeEvents()];
         for (int i = 0; i < numTimeEvents(); i++)
             samples[i] = NULL;
     }
     if (numDelays() > 0)
     {
         delays = new AdevsDelayData*[numDelays()];
         for (int i = 0; i < numDelays(); i++)
             delays[i] = NULL;
     }
     if (numMathEvents() > 0)
     {
         eventFuncs = new AdevsMathEventFunc*[numMathEvents()];
         for (int i = 0; i < numMathEvents(); i++)
             eventFuncs[i] = NULL;
     }
 }

 BuildingModel::~BuildingModel()
 {
      if (zc != NULL) delete [] zc;
      if (samples != NULL)
      {
         for (int i = 0; i < numTimeEvents(); i++)
             if (samples[i] != NULL) delete samples[i];
         delete [] samples;
      }
      if (delays != NULL)
      {
         for (int i = 0; i < numDelays(); i++)
             if (delays[i] != NULL) delete delays[i];
         delete [] delays;
      }
      if (eventFuncs != NULL)
      {
         for (int i = 0; i < numMathEvents(); i++)
             if (eventFuncs[i] != NULL) delete eventFuncs[i];
         delete [] eventFuncs;
      }
 }
 

 static void static_initial_objective_func(long*, double* w, double* f)
 {
     active_model->initial_objective_func(w,f,1.0);
 }
 
 void BuildingModel::initial_objective_func(double* w, double *f, double $P$_lambda)
 {
     // Get new values for the unknown variables
     for (unsigned i = 0; i < init_unknown_vars.size(); i++)
     {
         if (w[i] != w[i]) MODELICA_TERMINATE("could not initialize unknown reals");
         *(init_unknown_vars[i]) = w[i];
     }
     // Calculate new state variable derivatives and algebraic variables
     bound_params();
     selectStateVars();
     calc_vars(NULL,true);
     // Calculate the new value of the objective function
     double r = 0.0;
     *f = 0.0;
     r=_t3-_PRE_t3; *f+=r*r;
     r=_t2-_PRE_t2; *f+=r*r;
     r=_t1-_PRE_t1; *f+=r*r;
     r=_energyUsed-_PRE_energyUsed; *f+=r*r;
     r=_DER_t3-_PRE_DER_t3; *f+=r*r;
     r=_DER_t2-_PRE_DER_t2; *f+=r*r;
     r=_DER_t1-_PRE_DER_t1; *f+=r*r;
     r=_DER_energyUsed-_PRE_DER_energyUsed; *f+=r*r;
     r=_C1-_PRE_C1; *f+=r*r;
     r=_C2-_PRE_C2; *f+=r*r;
     r=_C3-_PRE_C3; *f+=r*r;
     r=_K1-_PRE_K1; *f+=r*r;
     r=_K2-_PRE_K2; *f+=r*r;
     r=_K3-_PRE_K3; *f+=r*r;
     r=_K4-_PRE_K4; *f+=r*r;
     r=_K5-_PRE_K5; *f+=r*r;
     r=_solarGain-_PRE_solarGain; *f+=r*r;
     r=_heatHvac-_PRE_heatHvac; *f+=r*r;
     r=_coolHvac-_PRE_coolHvac; *f+=r*r;
 }
 
 void BuildingModel::solve_for_initial_unknowns()
 {
   init_unknown_vars.push_back(&_solarPower);
   init_unknown_vars.push_back(&_d3);
   init_unknown_vars.push_back(&_d2);
   init_unknown_vars.push_back(&_d1);
   init_unknown_vars.push_back(&_dayHour);
   init_unknown_vars.push_back(&_dayCycle);
   init_unknown_vars.push_back(&_day);
   if (!init_unknown_vars.empty())
   {
       long N = init_unknown_vars.size();
       long NPT = 2*N+2;
       double* w = new double[N];
       for (unsigned i = 0; i < init_unknown_vars.size(); i++)
           w[i] = *(init_unknown_vars[i]);
       double RHOBEG = 10.0;
       double RHOEND = 1.0E-7;
       long IPRINT = 0;
       long MAXFUN = 50000;
       double* scratch = new double[(NPT+13)*(NPT+N)+3*N*(N+3)/2];
       active_model = this;
       newuoa_(&N,&NPT,w,&RHOBEG,&RHOEND,&IPRINT,&MAXFUN,scratch,
               static_initial_objective_func);
       delete [] w;
       delete [] scratch;
   }
 }

 void BuildingModel::clear_event_flags()
 {
     for (int i = 0; i < numRelations(); i++) zc[i] = -1;
     for (int i = 0; i < numMathEvents(); i++)
         if (eventFuncs[i] != NULL) eventFuncs[i]->setInit(true);
 }
 
 void BuildingModel::init(double* q)
 {
     atInit = true;
     atEvent = false;
     timeValue = q[numVars()-1] = 0.0;
     clear_event_flags();
     // Get initial values as given in the model
     _t3=25.0;
     _t2=25.0;
     _t1=25.0;
     _energyUsed=0.0;
     _DER_t3=0.0;
     _DER_t2=0.0;
     _DER_t1=0.0;
     _DER_energyUsed=0.0;
     _solarPower=0.0;
     _d3=0.0;
     _d2=0.0;
     _d1=0.0;
     _dayHour=0.0;
     _dayCycle=0.0;
     _day=0.0;
     _C1=935600.0;
     _C2=2970000.0;
     _C3=669500.0;
     _K1=16.48;
     _K2=108.5;
     _K3=5.0;
     _K4=30.5;
     _K5=23.04;
     _solarGain=1.0;
     _heatHvac=100.0;
     _coolHvac=-100.0;
     _coolStage=0;
     _heatStage=0;
     // Save these to the old values so that pre() and edge() work
     save_vars();
     // Calculate any equations that provide initial values
     bound_params();
     // Solve for any remaining unknowns
     solve_for_initial_unknowns();
     selectStateVars();
     calc_vars();
     save_vars();
     q[0]=_t3;
     q[1]=_t2;
     q[2]=_t1;
     q[3]=_energyUsed;
     atInit = false;
     for (int i = 0; i < numMathEvents(); i++)
         if (eventFuncs[i] != NULL) eventFuncs[i]->setInit(false);
 }

 void BuildingModel::der_func(const double* q, double* dq)
 {
     calc_vars(q);
     dq[0]=_DER_t3;
     dq[1]=_DER_t2;
     dq[2]=_DER_t1;
     dq[3]=_DER_energyUsed;
     dq[numVars()-1] = 1.0;
     restore_vars();
 }

 void BuildingModel::postStep(double* q)
 {
     calc_vars(q);
     if (selectStateVars())
     {
         q[0] = _t3;
         q[1] = _t2;
         q[2] = _t1;
         q[3] = _energyUsed;
         calc_vars(q,true);
     }
     save_vars();
 }

 void BuildingModel::save_vars()
 {
   _PRE_timeValue = timeValue;
   _PRE_t3=_t3;
   _PRE_t2=_t2;
   _PRE_t1=_t1;
   _PRE_energyUsed=_energyUsed;
   _PRE_DER_t3=_DER_t3;
   _PRE_DER_t2=_DER_t2;
   _PRE_DER_t1=_DER_t1;
   _PRE_DER_energyUsed=_DER_energyUsed;
   _PRE_solarPower=_solarPower;
   _PRE_d3=_d3;
   _PRE_d2=_d2;
   _PRE_d1=_d1;
   _PRE_dayHour=_dayHour;
   _PRE_dayCycle=_dayCycle;
   _PRE_day=_day;
   _PRE_C1=_C1;
   _PRE_C2=_C2;
   _PRE_C3=_C3;
   _PRE_K1=_K1;
   _PRE_K2=_K2;
   _PRE_K3=_K3;
   _PRE_K4=_K4;
   _PRE_K5=_K5;
   _PRE_solarGain=_solarGain;
   _PRE_heatHvac=_heatHvac;
   _PRE_coolHvac=_coolHvac;
 }

 void BuildingModel::restore_vars()
 {
   timeValue = _PRE_timeValue;
   _t3=_PRE_t3;
   _t2=_PRE_t2;
   _t1=_PRE_t1;
   _energyUsed=_PRE_energyUsed;
   _DER_t3=_PRE_DER_t3;
   _DER_t2=_PRE_DER_t2;
   _DER_t1=_PRE_DER_t1;
   _DER_energyUsed=_PRE_DER_energyUsed;
   _solarPower=_PRE_solarPower;
   _d3=_PRE_d3;
   _d2=_PRE_d2;
   _d1=_PRE_d1;
   _dayHour=_PRE_dayHour;
   _dayCycle=_PRE_dayCycle;
   _day=_PRE_day;
     _C1=_PRE_C1;
     _C2=_PRE_C2;
     _C3=_PRE_C3;
     _K1=_PRE_K1;
     _K2=_PRE_K2;
     _K3=_PRE_K3;
     _K4=_PRE_K4;
     _K5=_PRE_K5;
     _solarGain=_PRE_solarGain;
     _heatHvac=_PRE_heatHvac;
     _coolHvac=_PRE_coolHvac;
 }

 void BuildingModel::calc_vars(const double* q, bool doReinit)
 {
     bool reInit = false;
     active_model = this;
     if (atEvent || doReinit) clear_event_flags();
     // Copy state variable arrays to values used in the odes
     if (q != NULL)
     {
         timeValue = q[numVars()-1];
         _t3=q[0];
         _t2=q[1];
         _t1=q[2];
         _energyUsed=q[3];
     }
     modelica_real tmp0;
     modelica_real tmp1;
     modelica_boolean tmp2;
     modelica_boolean tmp3;
     modelica_real tmp4;
     modelica_real tmp5;
     modelica_real tmp6;
     // Primary equations
     _day = (timeValue / 86400.0); 
     tmp0 = cos((6.28 * _day));
     _dayCycle = (0.5 + (tmp0 / 2.0)); 
     _d1 = (25.0 * _dayCycle); 
     _d2 = (40.0 * _dayCycle); 
     _solarPower = (_solarGain * _d2); 
     tmp1 = floor(_day, (modelica_integer) 0);
     _dayHour = (24.0 * (_day - tmp1)); 
     ADEVS_SAVEZEROCROSS(tmp2, _dayHour, 8.0, 0,>=);
     ADEVS_SAVEZEROCROSS(tmp3, _dayHour, 18.0, 1,<=);
     _d3 = ((tmp2 && tmp3)?80.0:0.0); 
     tmp4 = DIVISION(((_K5 * (_t1 - _t3)) + (_K4 * (_d1 - _t3))), _C3, _OMC_LIT2);
     _DER_t3 = tmp4; 
     tmp5 = DIVISION((((_K1 + _K2) * (_t1 - _t2)) + _d2), _C2, _OMC_LIT3);
     _DER_t2 = tmp5; 
     tmp6 = DIVISION((((_K1 + _K2) * (_t2 - _t1)) + ((_K5 * (_t3 - _t1)) + ((_K3 * (_d1 - _t1)) + ((_heatHvac * ((modelica_real)(modelica_integer)_heatStage)) + ((_coolHvac * ((modelica_real)(modelica_integer)_coolStage)) + (_d2 + _d3)))))), _C1, _OMC_LIT4);
     _DER_t1 = tmp6; 
     _DER_energyUsed = (fabs((_heatHvac * ((modelica_real)(modelica_integer)_heatStage))) + fabs((_coolHvac * ((modelica_real)(modelica_integer)_coolStage)))); 
     // Alias equations
     // Reinits
     // Alias assignments
     if (atEvent && !reInit) reInit = check_for_new_events();
     if (reInit)
     {
         save_vars();
         calc_vars(NULL,reInit);
     }
 }

 
 bool BuildingModel::check_for_new_events()
 {
   bool result = false;
   double* z = new double[numZeroCrossings()];
     ADEVS_ZEROCROSSING(0, Adevs_GreaterEq(_dayHour, 8.0));
     ADEVS_ZEROCROSSING(1, Adevs_LessEq(_dayHour, 18.0));
     z[numRelations()+2*(modelica_integer) 0] = eventFuncs[(modelica_integer) 0]->getZUp(_day);
     z[numRelations()+2*(modelica_integer) 0+1] = eventFuncs[(modelica_integer) 0]->getZDown(_day);
     // IN EVENT FUNCTION: UNKNOWN ZERO CROSSING for 1
     // ((_dayHour >= 8.0) && (_dayHour <= 18.0))
   for (int i = 0; i < numRelations() && !result; i++)
   {
     if (z[i] < 0.0 && zc[i] == 1) result = true;
     else if (z[i] > 0.0 && zc[i] == 0) result = true;
   }
   for (int i = numRelations(); i < numZeroCrossings() && !result; i += 2)
   {
       if (z[i] < 0.0 || z[i+1] < 0.0) result = true;
   }
   delete [] z;
   return result;
 }
 
 void BuildingModel::state_event_func(const double* q, double* z)
 {
     calc_vars(q);
     ADEVS_ZEROCROSSING(0, Adevs_GreaterEq(_dayHour, 8.0));
     ADEVS_ZEROCROSSING(1, Adevs_LessEq(_dayHour, 18.0));
     z[numRelations()+2*(modelica_integer) 0] = eventFuncs[(modelica_integer) 0]->getZUp(_day);
     z[numRelations()+2*(modelica_integer) 0+1] = eventFuncs[(modelica_integer) 0]->getZDown(_day);
     // IN EVENT FUNCTION: UNKNOWN ZERO CROSSING for 1
     // ((_dayHour >= 8.0) && (_dayHour <= 18.0))
     extra_state_event_funcs(&(z[numStateEvents()]));
     restore_vars();
 }
 
 bool BuildingModel::sample(int index, double tStart, double tInterval)
 {
   index--;
   assert(index >= 0);
     if (samples[index] == NULL)
         samples[index] = new AdevsSampleData(tStart,tInterval);
     return samples[index]->atEvent(timeValue,epsilon);
 }
 
 double BuildingModel::time_event_func(const double* q)
 {
     double ttgMin = adevs_inf<double>();
     for (int i = 0; i < numTimeEvents(); i++)
     {
         double ttg = samples[i]->timeToEvent(timeValue);
         if (ttg < ttgMin) ttgMin = ttg;
     }
     for (int i = 0; i < numDelays(); i++)
     {
         double ttg = delays[i]->getMaxDelay();
         if (ttg < ttgMin) ttgMin = ttg;
     }
     return ttgMin;
 }
 
 void BuildingModel::internal_event(double* q, const bool* state_event)
 {
     atEvent = true;
     for (int i = 0; i < numTimeEvents(); i++)
     {
         assert(samples[i] != NULL);
         samples[i]->setEnabled(true);
     }
     calc_vars(q);
     for (int i = 0; i < numTimeEvents(); i++)
     {
         samples[i]->update(timeValue,epsilon);
         samples[i]->setEnabled(false);
     }
     save_vars(); // save the new state of the model
     // Reinitialize state variables that need to be reinitialized
     q[0]=_t3;
     q[1]=_t2;
     q[2]=_t1;
     q[3]=_energyUsed;
     for (int i = 0; i < numMathEvents(); i++)
         if (eventFuncs[i] != NULL) eventFuncs[i]->setInit(false);
     atEvent = false;
 }
 
 double BuildingModel::floor(double expr, int index)
 {
     if (eventFuncs[index] == NULL)
         eventFuncs[index] = new AdevsFloorFunc(epsilon);
     return eventFuncs[index]->calcValue(expr);
 }
 
 double BuildingModel::div(double x, double y, int index)
 {
     if (eventFuncs[index] == NULL)
         eventFuncs[index] = new AdevsDivFunc(epsilon);
     return eventFuncs[index]->calcValue(x/y);
 }
 
 int BuildingModel::integer(double expr, int index)
 {
     if (eventFuncs[index] == NULL)
         eventFuncs[index] = new AdevsFloorFunc(epsilon);
     return int(eventFuncs[index]->calcValue(expr));
 }
 
 double BuildingModel::ceil(double expr, int index)
 {
     if (eventFuncs[index] == NULL)
         eventFuncs[index] = new AdevsCeilFunc(epsilon);
     return eventFuncs[index]->calcValue(expr);
 }


 bool BuildingModel::selectStateVars()
 {
     bool doReinit = false;
     return doReinit;
 }
 
 double BuildingModel::calcDelay(int index, double expr, double t, double delay)
 {
     if (delays[index] == NULL || !delays[index]->isEnabled()) return expr;
     else return delays[index]->sample(t-delay);
 }
 
 void BuildingModel::saveDelay(int index, double expr, double t, double max_delay)
  {
      if (delays[index] == NULL)
          delays[index] = new AdevsDelayData(max_delay);
      delays[index]->insert(t,expr);
  }
 

#include "CBC.h"
#include "adevs_modelica_runtime.h"
using namespace adevs;

// This is used by the residual functions
static CBC* active_model;


void CBC::bound_params()
{
}

CBC::CBC(
    int extra_state_events, double eventHys):
    ode_system<OMC_ADEVS_IO_TYPE>(
        4+1, // Number of state variables plus one for the clock
        0+2*0+extra_state_events // Number of state event functions
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

 CBC::~CBC()
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
 
 void CBC::initial_objective_func(double* w, double *f, double $P$_lambda)
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
     r=_z4_Troom-_PRE_z4_Troom; *f+=r*r;
     r=_z3_Troom-_PRE_z3_Troom; *f+=r*r;
     r=_z2_Troom-_PRE_z2_Troom; *f+=r*r;
     r=_z1_Troom-_PRE_z1_Troom; *f+=r*r;
     r=_DER_z4_Troom-_PRE_DER_z4_Troom; *f+=r*r;
     r=_DER_z3_Troom-_PRE_DER_z3_Troom; *f+=r*r;
     r=_DER_z2_Troom-_PRE_DER_z2_Troom; *f+=r*r;
     r=_DER_z1_Troom-_PRE_DER_z1_Troom; *f+=r*r;
     r=_link_KInterZone[0]-_PRE_link_KInterZone[0]; *f+=r*r;
     r=_link_KInterZone[1]-_PRE_link_KInterZone[1]; *f+=r*r;
     r=_link_KInterZone[2]-_PRE_link_KInterZone[2]; *f+=r*r;
     r=_link_KInterZone[3]-_PRE_link_KInterZone[3]; *f+=r*r;
     r=_z1_alpha-_PRE_z1_alpha; *f+=r*r;
     r=_z1_heatHvac-_PRE_z1_heatHvac; *f+=r*r;
     r=_z1_coolHvac-_PRE_z1_coolHvac; *f+=r*r;
     r=_z1_delta-_PRE_z1_delta; *f+=r*r;
     r=_z2_alpha-_PRE_z2_alpha; *f+=r*r;
     r=_z2_heatHvac-_PRE_z2_heatHvac; *f+=r*r;
     r=_z2_coolHvac-_PRE_z2_coolHvac; *f+=r*r;
     r=_z2_delta-_PRE_z2_delta; *f+=r*r;
     r=_z3_alpha-_PRE_z3_alpha; *f+=r*r;
     r=_z3_heatHvac-_PRE_z3_heatHvac; *f+=r*r;
     r=_z3_coolHvac-_PRE_z3_coolHvac; *f+=r*r;
     r=_z3_delta-_PRE_z3_delta; *f+=r*r;
     r=_z4_alpha-_PRE_z4_alpha; *f+=r*r;
     r=_z4_heatHvac-_PRE_z4_heatHvac; *f+=r*r;
     r=_z4_coolHvac-_PRE_z4_coolHvac; *f+=r*r;
     r=_z4_delta-_PRE_z4_delta; *f+=r*r;
 }
 
 void CBC::solve_for_initial_unknowns()
 {
   init_unknown_vars.push_back(&_link_Q[3]);
   init_unknown_vars.push_back(&_link_T[3]);
   init_unknown_vars.push_back(&_link_Q[2]);
   init_unknown_vars.push_back(&_link_T[2]);
   init_unknown_vars.push_back(&_link_Q[1]);
   init_unknown_vars.push_back(&_link_T[1]);
   init_unknown_vars.push_back(&_link_Q[0]);
   init_unknown_vars.push_back(&_link_T[0]);
   init_unknown_vars.push_back(&_outdoor_Tair);
   init_unknown_vars.push_back(&_outdoor_dayCycle);
   init_unknown_vars.push_back(&_outdoor_day);
   init_unknown_vars.push_back(&_z4_pin_Q);
   init_unknown_vars.push_back(&_z3_pin_Q);
   init_unknown_vars.push_back(&_z2_pin_Q);
   init_unknown_vars.push_back(&_z1_pin_Q);
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

 void CBC::clear_event_flags()
 {
     for (int i = 0; i < numRelations(); i++) zc[i] = -1;
     for (int i = 0; i < numMathEvents(); i++)
         if (eventFuncs[i] != NULL) eventFuncs[i]->setInit(true);
 }
 
 void CBC::init(double* q)
 {
     atInit = true;
     atEvent = false;
     timeValue = q[numVars()-1] = 0.0;
     clear_event_flags();
     // Get initial values as given in the model
     _z4_Troom=70.0;
     _z3_Troom=70.0;
     _z2_Troom=70.0;
     _z1_Troom=70.0;
     _DER_z4_Troom=0.0;
     _DER_z3_Troom=0.0;
     _DER_z2_Troom=0.0;
     _DER_z1_Troom=0.0;
     _link_Q[3]=0.0;
     _link_T[3]=0.0;
     _link_Q[2]=0.0;
     _link_T[2]=0.0;
     _link_Q[1]=0.0;
     _link_T[1]=0.0;
     _link_Q[0]=0.0;
     _link_T[0]=0.0;
     _outdoor_Tair=0.0;
     _outdoor_dayCycle=0.0;
     _outdoor_day=0.0;
     _z4_pin_Q=0.0;
     _z3_pin_Q=0.0;
     _z2_pin_Q=0.0;
     _z1_pin_Q=0.0;
     _link_KInterZone[0]=1000.0;
     _link_KInterZone[1]=1000.0;
     _link_KInterZone[2]=1000.0;
     _link_KInterZone[3]=1000.0;
     _z1_alpha=0.000028;
     _z1_heatHvac=0.008;
     _z1_coolHvac=-0.008;
     _z1_delta=0.0;
     _z2_alpha=0.0000035;
     _z2_heatHvac=0.008;
     _z2_coolHvac=-0.008;
     _z2_delta=0.0;
     _z3_alpha=0.033;
     _z3_heatHvac=0.008;
     _z3_coolHvac=-0.008;
     _z3_delta=0.0;
     _z4_alpha=0.0000035;
     _z4_heatHvac=0.008;
     _z4_coolHvac=-0.008;
     _z4_delta=0.0;
     _z1_heatStage=0;
     _z1_coolStage=0;
     _z2_heatStage=0;
     _z2_coolStage=0;
     _z3_heatStage=0;
     _z3_coolStage=0;
     _z4_heatStage=0;
     _z4_coolStage=0;
     // Save these to the old values so that pre() and edge() work
     save_vars();
     // Calculate any equations that provide initial values
     bound_params();
     // Solve for any remaining unknowns
     solve_for_initial_unknowns();
     selectStateVars();
     calc_vars();
     save_vars();
     q[0]=_z4_Troom;
     q[1]=_z3_Troom;
     q[2]=_z2_Troom;
     q[3]=_z1_Troom;
     atInit = false;
     for (int i = 0; i < numMathEvents(); i++)
         if (eventFuncs[i] != NULL) eventFuncs[i]->setInit(false);
 }

 void CBC::der_func(const double* q, double* dq)
 {
     calc_vars(q);
     dq[0]=_DER_z4_Troom;
     dq[1]=_DER_z3_Troom;
     dq[2]=_DER_z2_Troom;
     dq[3]=_DER_z1_Troom;
     dq[numVars()-1] = 1.0;
     restore_vars();
 }

 void CBC::postStep(double* q)
 {
     calc_vars(q);
     if (selectStateVars())
     {
         q[0] = _z4_Troom;
         q[1] = _z3_Troom;
         q[2] = _z2_Troom;
         q[3] = _z1_Troom;
         calc_vars(q,true);
     }
     save_vars();
 }

 void CBC::save_vars()
 {
   _PRE_timeValue = timeValue;
   _PRE_z4_Troom=_z4_Troom;
   _PRE_z3_Troom=_z3_Troom;
   _PRE_z2_Troom=_z2_Troom;
   _PRE_z1_Troom=_z1_Troom;
   _PRE_DER_z4_Troom=_DER_z4_Troom;
   _PRE_DER_z3_Troom=_DER_z3_Troom;
   _PRE_DER_z2_Troom=_DER_z2_Troom;
   _PRE_DER_z1_Troom=_DER_z1_Troom;
   _PRE_link_Q[3]=_link_Q[3];
   _PRE_link_T[3]=_link_T[3];
   _PRE_link_Q[2]=_link_Q[2];
   _PRE_link_T[2]=_link_T[2];
   _PRE_link_Q[1]=_link_Q[1];
   _PRE_link_T[1]=_link_T[1];
   _PRE_link_Q[0]=_link_Q[0];
   _PRE_link_T[0]=_link_T[0];
   _PRE_outdoor_Tair=_outdoor_Tair;
   _PRE_outdoor_dayCycle=_outdoor_dayCycle;
   _PRE_outdoor_day=_outdoor_day;
   _PRE_z4_pin_Q=_z4_pin_Q;
   _PRE_z3_pin_Q=_z3_pin_Q;
   _PRE_z2_pin_Q=_z2_pin_Q;
   _PRE_z1_pin_Q=_z1_pin_Q;
   _PRE_link_pb_T[2]=_link_pb_T[2];
   _PRE_link_pa_T[3]=_link_pa_T[3];
   _PRE_link_pb_T[1]=_link_pb_T[1];
   _PRE_link_pa_T[2]=_link_pa_T[2];
   _PRE_link_pb_T[0]=_link_pb_T[0];
   _PRE_link_pa_T[1]=_link_pa_T[1];
   _PRE_link_pa_T[0]=_link_pa_T[0];
   _PRE_link_pb_T[3]=_link_pb_T[3];
   _PRE_link_pa_Q[3]=_link_pa_Q[3];
   _PRE_link_pb_Q[3]=_link_pb_Q[3];
   _PRE_link_pa_Q[2]=_link_pa_Q[2];
   _PRE_link_pb_Q[2]=_link_pb_Q[2];
   _PRE_link_pa_Q[1]=_link_pa_Q[1];
   _PRE_link_pb_Q[1]=_link_pb_Q[1];
   _PRE_link_pa_Q[0]=_link_pa_Q[0];
   _PRE_link_pb_Q[0]=_link_pb_Q[0];
   _PRE_z4_pin_T=_z4_pin_T;
   _PRE_z3_pin_T=_z3_pin_T;
   _PRE_z2_pin_T=_z2_pin_T;
   _PRE_z1_pin_T=_z1_pin_T;
   _PRE_z4_Tair=_z4_Tair;
   _PRE_z3_Tair=_z3_Tair;
   _PRE_z2_Tair=_z2_Tair;
   _PRE_z1_Tair=_z1_Tair;
   _PRE_link_KInterZone[0]=_link_KInterZone[0];
   _PRE_link_KInterZone[1]=_link_KInterZone[1];
   _PRE_link_KInterZone[2]=_link_KInterZone[2];
   _PRE_link_KInterZone[3]=_link_KInterZone[3];
   _PRE_z1_alpha=_z1_alpha;
   _PRE_z1_heatHvac=_z1_heatHvac;
   _PRE_z1_coolHvac=_z1_coolHvac;
   _PRE_z1_delta=_z1_delta;
   _PRE_z2_alpha=_z2_alpha;
   _PRE_z2_heatHvac=_z2_heatHvac;
   _PRE_z2_coolHvac=_z2_coolHvac;
   _PRE_z2_delta=_z2_delta;
   _PRE_z3_alpha=_z3_alpha;
   _PRE_z3_heatHvac=_z3_heatHvac;
   _PRE_z3_coolHvac=_z3_coolHvac;
   _PRE_z3_delta=_z3_delta;
   _PRE_z4_alpha=_z4_alpha;
   _PRE_z4_heatHvac=_z4_heatHvac;
   _PRE_z4_coolHvac=_z4_coolHvac;
   _PRE_z4_delta=_z4_delta;
 }

 void CBC::restore_vars()
 {
   timeValue = _PRE_timeValue;
   _z4_Troom=_PRE_z4_Troom;
   _z3_Troom=_PRE_z3_Troom;
   _z2_Troom=_PRE_z2_Troom;
   _z1_Troom=_PRE_z1_Troom;
   _DER_z4_Troom=_PRE_DER_z4_Troom;
   _DER_z3_Troom=_PRE_DER_z3_Troom;
   _DER_z2_Troom=_PRE_DER_z2_Troom;
   _DER_z1_Troom=_PRE_DER_z1_Troom;
   _link_Q[3]=_PRE_link_Q[3];
   _link_T[3]=_PRE_link_T[3];
   _link_Q[2]=_PRE_link_Q[2];
   _link_T[2]=_PRE_link_T[2];
   _link_Q[1]=_PRE_link_Q[1];
   _link_T[1]=_PRE_link_T[1];
   _link_Q[0]=_PRE_link_Q[0];
   _link_T[0]=_PRE_link_T[0];
   _outdoor_Tair=_PRE_outdoor_Tair;
   _outdoor_dayCycle=_PRE_outdoor_dayCycle;
   _outdoor_day=_PRE_outdoor_day;
   _z4_pin_Q=_PRE_z4_pin_Q;
   _z3_pin_Q=_PRE_z3_pin_Q;
   _z2_pin_Q=_PRE_z2_pin_Q;
   _z1_pin_Q=_PRE_z1_pin_Q;
   _link_pb_T[2]=_PRE_link_pb_T[2];
   _link_pa_T[3]=_PRE_link_pa_T[3];
   _link_pb_T[1]=_PRE_link_pb_T[1];
   _link_pa_T[2]=_PRE_link_pa_T[2];
   _link_pb_T[0]=_PRE_link_pb_T[0];
   _link_pa_T[1]=_PRE_link_pa_T[1];
   _link_pa_T[0]=_PRE_link_pa_T[0];
   _link_pb_T[3]=_PRE_link_pb_T[3];
   _link_pa_Q[3]=_PRE_link_pa_Q[3];
   _link_pb_Q[3]=_PRE_link_pb_Q[3];
   _link_pa_Q[2]=_PRE_link_pa_Q[2];
   _link_pb_Q[2]=_PRE_link_pb_Q[2];
   _link_pa_Q[1]=_PRE_link_pa_Q[1];
   _link_pb_Q[1]=_PRE_link_pb_Q[1];
   _link_pa_Q[0]=_PRE_link_pa_Q[0];
   _link_pb_Q[0]=_PRE_link_pb_Q[0];
   _z4_pin_T=_PRE_z4_pin_T;
   _z3_pin_T=_PRE_z3_pin_T;
   _z2_pin_T=_PRE_z2_pin_T;
   _z1_pin_T=_PRE_z1_pin_T;
   _z4_Tair=_PRE_z4_Tair;
   _z3_Tair=_PRE_z3_Tair;
   _z2_Tair=_PRE_z2_Tair;
   _z1_Tair=_PRE_z1_Tair;
     _link_KInterZone[0]=_PRE_link_KInterZone[0];
     _link_KInterZone[1]=_PRE_link_KInterZone[1];
     _link_KInterZone[2]=_PRE_link_KInterZone[2];
     _link_KInterZone[3]=_PRE_link_KInterZone[3];
     _z1_alpha=_PRE_z1_alpha;
     _z1_heatHvac=_PRE_z1_heatHvac;
     _z1_coolHvac=_PRE_z1_coolHvac;
     _z1_delta=_PRE_z1_delta;
     _z2_alpha=_PRE_z2_alpha;
     _z2_heatHvac=_PRE_z2_heatHvac;
     _z2_coolHvac=_PRE_z2_coolHvac;
     _z2_delta=_PRE_z2_delta;
     _z3_alpha=_PRE_z3_alpha;
     _z3_heatHvac=_PRE_z3_heatHvac;
     _z3_coolHvac=_PRE_z3_coolHvac;
     _z3_delta=_PRE_z3_delta;
     _z4_alpha=_PRE_z4_alpha;
     _z4_heatHvac=_PRE_z4_heatHvac;
     _z4_coolHvac=_PRE_z4_coolHvac;
     _z4_delta=_PRE_z4_delta;
 }

 void CBC::calc_vars(const double* q, bool doReinit)
 {
     bool reInit = false;
     active_model = this;
     if (atEvent || doReinit) clear_event_flags();
     // Copy state variable arrays to values used in the odes
     if (q != NULL)
     {
         timeValue = q[numVars()-1];
         _z4_Troom=q[0];
         _z3_Troom=q[1];
         _z2_Troom=q[2];
         _z1_Troom=q[3];
     }
     modelica_real tmp0;
     // Primary equations
     _link_T[0] = (_z1_Troom - _z2_Troom); 
     _link_Q[0] = (_link_KInterZone[0] * _link_T[0]); 
     _link_T[1] = (_z2_Troom - _z3_Troom); 
     _link_Q[1] = (_link_KInterZone[1] * _link_T[1]); 
     _link_T[2] = (_z3_Troom - _z4_Troom); 
     _link_Q[2] = (_link_KInterZone[2] * _link_T[2]); 
     _link_T[3] = (_z4_Troom - _z1_Troom); 
     _link_Q[3] = (_link_KInterZone[3] * _link_T[3]); 
     _outdoor_day = (timeValue / 86400.0); 
     tmp0 = cos((6.28 * _outdoor_day));
     _outdoor_dayCycle = (0.5 + (tmp0 / 2.0)); 
     _outdoor_Tair = (68.0 + (20.0 * _outdoor_dayCycle)); 
     _z1_pin_Q = (_link_Q[3] - _link_Q[0]); 
     _DER_z1_Troom = ((_z1_alpha * (_outdoor_Tair - _z1_Troom)) + ((((modelica_real)(modelica_integer)_z1_heatStage) * _z1_heatHvac) + ((((modelica_real)(modelica_integer)_z1_coolStage) * _z1_coolHvac) + (_z1_pin_Q + _z1_delta)))); 
     _z2_pin_Q = (_link_Q[0] - _link_Q[1]); 
     _DER_z2_Troom = ((_z2_alpha * (_outdoor_Tair - _z2_Troom)) + ((((modelica_real)(modelica_integer)_z2_heatStage) * _z2_heatHvac) + ((((modelica_real)(modelica_integer)_z2_coolStage) * _z2_coolHvac) + (_z2_pin_Q + _z2_delta)))); 
     _z3_pin_Q = (_link_Q[1] - _link_Q[2]); 
     _DER_z3_Troom = ((_z3_alpha * (_outdoor_Tair - _z3_Troom)) + ((((modelica_real)(modelica_integer)_z3_heatStage) * _z3_heatHvac) + ((((modelica_real)(modelica_integer)_z3_coolStage) * _z3_coolHvac) + (_z3_pin_Q + _z3_delta)))); 
     _z4_pin_Q = (_link_Q[2] - _link_Q[3]); 
     _DER_z4_Troom = ((_z4_alpha * (_outdoor_Tair - _z4_Troom)) + ((((modelica_real)(modelica_integer)_z4_heatStage) * _z4_heatHvac) + ((((modelica_real)(modelica_integer)_z4_coolStage) * _z4_coolHvac) + (_z4_pin_Q + _z4_delta)))); 
     // Alias equations
     // Reinits
     // Alias assignments
     _link_pb_T[2] = _z4_Troom;
     _link_pa_T[3] = _z4_Troom;
     _link_pb_T[1] = _z3_Troom;
     _link_pa_T[2] = _z3_Troom;
     _link_pb_T[0] = _z2_Troom;
     _link_pa_T[1] = _z2_Troom;
     _link_pa_T[0] = _z1_Troom;
     _link_pb_T[3] = _z1_Troom;
     _link_pa_Q[3] = _link_Q[3];
     _link_pb_Q[3] = _link_Q[3];
     _link_pa_Q[2] = _link_Q[2];
     _link_pb_Q[2] = _link_Q[2];
     _link_pa_Q[1] = _link_Q[1];
     _link_pb_Q[1] = _link_Q[1];
     _link_pa_Q[0] = _link_Q[0];
     _link_pb_Q[0] = _link_Q[0];
     _z4_pin_T = _z4_Troom;
     _z3_pin_T = _z3_Troom;
     _z2_pin_T = _z2_Troom;
     _z1_pin_T = _z1_Troom;
     _z4_Tair = _outdoor_Tair;
     _z3_Tair = _outdoor_Tair;
     _z2_Tair = _outdoor_Tair;
     _z1_Tair = _outdoor_Tair;
     if (atEvent && !reInit) reInit = check_for_new_events();
     if (reInit)
     {
         save_vars();
         calc_vars(NULL,reInit);
     }
 }

 
 bool CBC::check_for_new_events()
 {
   bool result = false;
   double* z = new double[numZeroCrossings()];
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
 
 void CBC::state_event_func(const double* q, double* z)
 {
     calc_vars(q);
     extra_state_event_funcs(&(z[numStateEvents()]));
     restore_vars();
 }
 
 bool CBC::sample(int index, double tStart, double tInterval)
 {
   index--;
   assert(index >= 0);
     if (samples[index] == NULL)
         samples[index] = new AdevsSampleData(tStart,tInterval);
     return samples[index]->atEvent(timeValue,epsilon);
 }
 
 double CBC::time_event_func(const double* q)
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
 
 void CBC::internal_event(double* q, const bool* state_event)
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
     q[0]=_z4_Troom;
     q[1]=_z3_Troom;
     q[2]=_z2_Troom;
     q[3]=_z1_Troom;
     for (int i = 0; i < numMathEvents(); i++)
         if (eventFuncs[i] != NULL) eventFuncs[i]->setInit(false);
     atEvent = false;
 }
 
 double CBC::floor(double expr, int index)
 {
     if (eventFuncs[index] == NULL)
         eventFuncs[index] = new AdevsFloorFunc(epsilon);
     return eventFuncs[index]->calcValue(expr);
 }
 
 double CBC::div(double x, double y, int index)
 {
     if (eventFuncs[index] == NULL)
         eventFuncs[index] = new AdevsDivFunc(epsilon);
     return eventFuncs[index]->calcValue(x/y);
 }
 
 int CBC::integer(double expr, int index)
 {
     if (eventFuncs[index] == NULL)
         eventFuncs[index] = new AdevsFloorFunc(epsilon);
     return int(eventFuncs[index]->calcValue(expr));
 }
 
 double CBC::ceil(double expr, int index)
 {
     if (eventFuncs[index] == NULL)
         eventFuncs[index] = new AdevsCeilFunc(epsilon);
     return eventFuncs[index]->calcValue(expr);
 }


 bool CBC::selectStateVars()
 {
     bool doReinit = false;
     return doReinit;
 }
 
 double CBC::calcDelay(int index, double expr, double t, double delay)
 {
     if (delays[index] == NULL || !delays[index]->isEnabled()) return expr;
     else return delays[index]->sample(t-delay);
 }
 
 void CBC::saveDelay(int index, double expr, double t, double max_delay)
  {
      if (delays[index] == NULL)
          delays[index] = new AdevsDelayData(max_delay);
      delays[index]->insert(t,expr);
  }
 

#include "FourZoneBuilding.h"
#include "adevs_modelica_runtime.h"
using namespace adevs;

// This is used by the residual functions
static FourZoneBuilding* active_model;


void FourZoneBuilding::bound_params()
{
    _z1_d3 = 0.0; 
    _z2_d3 = 0.0; 
    _z3_d3 = 0.0; 
    _z4_d3 = 0.0; 
    _znoise_d3 = 0.0; 
}

FourZoneBuilding::FourZoneBuilding(
    int extra_state_events, double eventHys):
    ode_system<OMC_ADEVS_IO_TYPE>(
        20+1, // Number of state variables plus one for the clock
        0+2*1+extra_state_events // Number of state event functions
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

 FourZoneBuilding::~FourZoneBuilding()
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
 
 void FourZoneBuilding::initial_objective_func(double* w, double *f, double $P$_lambda)
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
     r=_z1_energyUsed-_PRE_z1_energyUsed; *f+=r*r;
     r=_z2_energyUsed-_PRE_z2_energyUsed; *f+=r*r;
     r=_z3_energyUsed-_PRE_z3_energyUsed; *f+=r*r;
     r=_z4_energyUsed-_PRE_z4_energyUsed; *f+=r*r;
     r=_znoise_energyUsed-_PRE_znoise_energyUsed; *f+=r*r;
     r=_znoise_t3-_PRE_znoise_t3; *f+=r*r;
     r=_znoise_t2-_PRE_znoise_t2; *f+=r*r;
     r=_znoise_t1-_PRE_znoise_t1; *f+=r*r;
     r=_z4_t3-_PRE_z4_t3; *f+=r*r;
     r=_z4_t2-_PRE_z4_t2; *f+=r*r;
     r=_z4_t1-_PRE_z4_t1; *f+=r*r;
     r=_z3_t3-_PRE_z3_t3; *f+=r*r;
     r=_z3_t2-_PRE_z3_t2; *f+=r*r;
     r=_z3_t1-_PRE_z3_t1; *f+=r*r;
     r=_z2_t3-_PRE_z2_t3; *f+=r*r;
     r=_z2_t2-_PRE_z2_t2; *f+=r*r;
     r=_z2_t1-_PRE_z2_t1; *f+=r*r;
     r=_z1_t3-_PRE_z1_t3; *f+=r*r;
     r=_z1_t2-_PRE_z1_t2; *f+=r*r;
     r=_z1_t1-_PRE_z1_t1; *f+=r*r;
     r=_DER_z1_energyUsed-_PRE_DER_z1_energyUsed; *f+=r*r;
     r=_DER_z2_energyUsed-_PRE_DER_z2_energyUsed; *f+=r*r;
     r=_DER_z3_energyUsed-_PRE_DER_z3_energyUsed; *f+=r*r;
     r=_DER_z4_energyUsed-_PRE_DER_z4_energyUsed; *f+=r*r;
     r=_DER_znoise_energyUsed-_PRE_DER_znoise_energyUsed; *f+=r*r;
     r=_DER_znoise_t3-_PRE_DER_znoise_t3; *f+=r*r;
     r=_DER_znoise_t2-_PRE_DER_znoise_t2; *f+=r*r;
     r=_DER_znoise_t1-_PRE_DER_znoise_t1; *f+=r*r;
     r=_DER_z4_t3-_PRE_DER_z4_t3; *f+=r*r;
     r=_DER_z4_t2-_PRE_DER_z4_t2; *f+=r*r;
     r=_DER_z4_t1-_PRE_DER_z4_t1; *f+=r*r;
     r=_DER_z3_t3-_PRE_DER_z3_t3; *f+=r*r;
     r=_DER_z3_t2-_PRE_DER_z3_t2; *f+=r*r;
     r=_DER_z3_t1-_PRE_DER_z3_t1; *f+=r*r;
     r=_DER_z2_t3-_PRE_DER_z2_t3; *f+=r*r;
     r=_DER_z2_t2-_PRE_DER_z2_t2; *f+=r*r;
     r=_DER_z2_t1-_PRE_DER_z2_t1; *f+=r*r;
     r=_DER_z1_t3-_PRE_DER_z1_t3; *f+=r*r;
     r=_DER_z1_t2-_PRE_DER_z1_t2; *f+=r*r;
     r=_DER_z1_t1-_PRE_DER_z1_t1; *f+=r*r;
     r=_link_KInterZone[0]-_PRE_link_KInterZone[0]; *f+=r*r;
     r=_link_KInterZone[1]-_PRE_link_KInterZone[1]; *f+=r*r;
     r=_link_KInterZone[2]-_PRE_link_KInterZone[2]; *f+=r*r;
     r=_link_KInterZone[3]-_PRE_link_KInterZone[3]; *f+=r*r;
     r=_link_KInterZone[4]-_PRE_link_KInterZone[4]; *f+=r*r;
     r=_z1_C1-_PRE_z1_C1; *f+=r*r;
     r=_z1_C2-_PRE_z1_C2; *f+=r*r;
     r=_z1_C3-_PRE_z1_C3; *f+=r*r;
     r=_z1_K1-_PRE_z1_K1; *f+=r*r;
     r=_z1_K2-_PRE_z1_K2; *f+=r*r;
     r=_z1_K3-_PRE_z1_K3; *f+=r*r;
     r=_z1_K4-_PRE_z1_K4; *f+=r*r;
     r=_z1_K5-_PRE_z1_K5; *f+=r*r;
     r=_z1_heatHvac-_PRE_z1_heatHvac; *f+=r*r;
     r=_z1_coolHvac-_PRE_z1_coolHvac; *f+=r*r;
     r=_z2_C1-_PRE_z2_C1; *f+=r*r;
     r=_z2_C2-_PRE_z2_C2; *f+=r*r;
     r=_z2_C3-_PRE_z2_C3; *f+=r*r;
     r=_z2_K1-_PRE_z2_K1; *f+=r*r;
     r=_z2_K2-_PRE_z2_K2; *f+=r*r;
     r=_z2_K3-_PRE_z2_K3; *f+=r*r;
     r=_z2_K4-_PRE_z2_K4; *f+=r*r;
     r=_z2_K5-_PRE_z2_K5; *f+=r*r;
     r=_z2_heatHvac-_PRE_z2_heatHvac; *f+=r*r;
     r=_z2_coolHvac-_PRE_z2_coolHvac; *f+=r*r;
     r=_z3_C1-_PRE_z3_C1; *f+=r*r;
     r=_z3_C2-_PRE_z3_C2; *f+=r*r;
     r=_z3_C3-_PRE_z3_C3; *f+=r*r;
     r=_z3_K1-_PRE_z3_K1; *f+=r*r;
     r=_z3_K2-_PRE_z3_K2; *f+=r*r;
     r=_z3_K3-_PRE_z3_K3; *f+=r*r;
     r=_z3_K4-_PRE_z3_K4; *f+=r*r;
     r=_z3_K5-_PRE_z3_K5; *f+=r*r;
     r=_z3_heatHvac-_PRE_z3_heatHvac; *f+=r*r;
     r=_z3_coolHvac-_PRE_z3_coolHvac; *f+=r*r;
     r=_z4_C1-_PRE_z4_C1; *f+=r*r;
     r=_z4_C2-_PRE_z4_C2; *f+=r*r;
     r=_z4_C3-_PRE_z4_C3; *f+=r*r;
     r=_z4_K1-_PRE_z4_K1; *f+=r*r;
     r=_z4_K2-_PRE_z4_K2; *f+=r*r;
     r=_z4_K3-_PRE_z4_K3; *f+=r*r;
     r=_z4_K4-_PRE_z4_K4; *f+=r*r;
     r=_z4_K5-_PRE_z4_K5; *f+=r*r;
     r=_z4_heatHvac-_PRE_z4_heatHvac; *f+=r*r;
     r=_z4_coolHvac-_PRE_z4_coolHvac; *f+=r*r;
     r=_znoise_C1-_PRE_znoise_C1; *f+=r*r;
     r=_znoise_C2-_PRE_znoise_C2; *f+=r*r;
     r=_znoise_C3-_PRE_znoise_C3; *f+=r*r;
     r=_znoise_K1-_PRE_znoise_K1; *f+=r*r;
     r=_znoise_K2-_PRE_znoise_K2; *f+=r*r;
     r=_znoise_K3-_PRE_znoise_K3; *f+=r*r;
     r=_znoise_K4-_PRE_znoise_K4; *f+=r*r;
     r=_znoise_K5-_PRE_znoise_K5; *f+=r*r;
     r=_znoise_heatHvac-_PRE_znoise_heatHvac; *f+=r*r;
     r=_znoise_coolHvac-_PRE_znoise_coolHvac; *f+=r*r;
 }
 
 void FourZoneBuilding::solve_for_initial_unknowns()
 {
   init_unknown_vars.push_back(&_link_Q[4]);
   init_unknown_vars.push_back(&_link_T[4]);
   init_unknown_vars.push_back(&_link_Q[3]);
   init_unknown_vars.push_back(&_link_T[3]);
   init_unknown_vars.push_back(&_link_Q[2]);
   init_unknown_vars.push_back(&_link_T[2]);
   init_unknown_vars.push_back(&_link_Q[1]);
   init_unknown_vars.push_back(&_link_T[1]);
   init_unknown_vars.push_back(&_link_Q[0]);
   init_unknown_vars.push_back(&_link_T[0]);
   init_unknown_vars.push_back(&_outdoor_d2);
   init_unknown_vars.push_back(&_outdoor_d1);
   init_unknown_vars.push_back(&_outdoor_dayHour);
   init_unknown_vars.push_back(&_outdoor_dayCycle);
   init_unknown_vars.push_back(&_outdoor_day);
   init_unknown_vars.push_back(&_z4_pin_Q);
   init_unknown_vars.push_back(&_z3_pin_Q);
   init_unknown_vars.push_back(&_z2_pin_Q);
   init_unknown_vars.push_back(&_z1_pin_Q);
   init_unknown_vars.push_back(&_z1_d3);
   init_unknown_vars.push_back(&_z2_d3);
   init_unknown_vars.push_back(&_z3_d3);
   init_unknown_vars.push_back(&_z4_d3);
   init_unknown_vars.push_back(&_znoise_d3);
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

 void FourZoneBuilding::clear_event_flags()
 {
     for (int i = 0; i < numRelations(); i++) zc[i] = -1;
     for (int i = 0; i < numMathEvents(); i++)
         if (eventFuncs[i] != NULL) eventFuncs[i]->setInit(true);
 }
 
 void FourZoneBuilding::init(double* q)
 {
     atInit = true;
     atEvent = false;
     timeValue = q[numVars()-1] = 0.0;
     clear_event_flags();
     // Get initial values as given in the model
     _z1_energyUsed=0.0;
     _z2_energyUsed=0.0;
     _z3_energyUsed=0.0;
     _z4_energyUsed=0.0;
     _znoise_energyUsed=0.0;
     _znoise_t3=25.0;
     _znoise_t2=25.0;
     _znoise_t1=25.0;
     _z4_t3=25.0;
     _z4_t2=25.0;
     _z4_t1=25.0;
     _z3_t3=25.0;
     _z3_t2=25.0;
     _z3_t1=25.0;
     _z2_t3=25.0;
     _z2_t2=25.0;
     _z2_t1=25.0;
     _z1_t3=25.0;
     _z1_t2=25.0;
     _z1_t1=25.0;
     _DER_z1_energyUsed=0.0;
     _DER_z2_energyUsed=0.0;
     _DER_z3_energyUsed=0.0;
     _DER_z4_energyUsed=0.0;
     _DER_znoise_energyUsed=0.0;
     _DER_znoise_t3=0.0;
     _DER_znoise_t2=0.0;
     _DER_znoise_t1=0.0;
     _DER_z4_t3=0.0;
     _DER_z4_t2=0.0;
     _DER_z4_t1=0.0;
     _DER_z3_t3=0.0;
     _DER_z3_t2=0.0;
     _DER_z3_t1=0.0;
     _DER_z2_t3=0.0;
     _DER_z2_t2=0.0;
     _DER_z2_t1=0.0;
     _DER_z1_t3=0.0;
     _DER_z1_t2=0.0;
     _DER_z1_t1=0.0;
     _link_Q[4]=0.0;
     _link_T[4]=0.0;
     _link_Q[3]=0.0;
     _link_T[3]=0.0;
     _link_Q[2]=0.0;
     _link_T[2]=0.0;
     _link_Q[1]=0.0;
     _link_T[1]=0.0;
     _link_Q[0]=0.0;
     _link_T[0]=0.0;
     _outdoor_d2=0.0;
     _outdoor_d1=0.0;
     _outdoor_dayHour=0.0;
     _outdoor_dayCycle=0.0;
     _outdoor_day=0.0;
     _z4_pin_Q=0.0;
     _z3_pin_Q=0.0;
     _z2_pin_Q=0.0;
     _z1_pin_Q=0.0;
     _z1_d3=0.0;
     _z2_d3=0.0;
     _z3_d3=0.0;
     _z4_d3=0.0;
     _znoise_d3=0.0;
     _link_KInterZone[0]=1000.0;
     _link_KInterZone[1]=1000.0;
     _link_KInterZone[2]=1000.0;
     _link_KInterZone[3]=1000.0;
     _link_KInterZone[4]=1000.0;
     _z1_C1=935600.0;
     _z1_C2=2970000.0;
     _z1_C3=669500.0;
     _z1_K1=16.48;
     _z1_K2=108.5;
     _z1_K3=5.0;
     _z1_K4=30.5;
     _z1_K5=23.04;
     _z1_heatHvac=100.0;
     _z1_coolHvac=-100.0;
     _z2_C1=935600.0;
     _z2_C2=2970000.0;
     _z2_C3=669500.0;
     _z2_K1=16.48;
     _z2_K2=108.5;
     _z2_K3=5.0;
     _z2_K4=30.5;
     _z2_K5=23.04;
     _z2_heatHvac=100.0;
     _z2_coolHvac=-100.0;
     _z3_C1=935600.0;
     _z3_C2=2970000.0;
     _z3_C3=669500.0;
     _z3_K1=16.48;
     _z3_K2=108.5;
     _z3_K3=5.0;
     _z3_K4=30.5;
     _z3_K5=23.04;
     _z3_heatHvac=100.0;
     _z3_coolHvac=-100.0;
     _z4_C1=935600.0;
     _z4_C2=2970000.0;
     _z4_C3=669500.0;
     _z4_K1=16.48;
     _z4_K2=108.5;
     _z4_K3=5.0;
     _z4_K4=30.5;
     _z4_K5=23.04;
     _z4_heatHvac=100.0;
     _z4_coolHvac=-100.0;
     _znoise_C1=935600.0;
     _znoise_C2=10000.0;
     _znoise_C3=669500.0;
     _znoise_K1=16.48;
     _znoise_K2=10.0;
     _znoise_K3=5.0;
     _znoise_K4=30.5;
     _znoise_K5=23.04;
     _znoise_heatHvac=100.0;
     _znoise_coolHvac=-100.0;
     _z1_heatStage=0;
     _z1_coolStage=0;
     _z2_heatStage=0;
     _z2_coolStage=0;
     _z3_heatStage=0;
     _z3_coolStage=0;
     _z4_heatStage=0;
     _z4_coolStage=0;
     _znoise_heatStage=0;
     _znoise_coolStage=0;
     // Save these to the old values so that pre() and edge() work
     save_vars();
     // Calculate any equations that provide initial values
     bound_params();
     // Solve for any remaining unknowns
     solve_for_initial_unknowns();
     selectStateVars();
     calc_vars();
     save_vars();
     q[0]=_z1_energyUsed;
     q[1]=_z2_energyUsed;
     q[2]=_z3_energyUsed;
     q[3]=_z4_energyUsed;
     q[4]=_znoise_energyUsed;
     q[5]=_znoise_t3;
     q[6]=_znoise_t2;
     q[7]=_znoise_t1;
     q[8]=_z4_t3;
     q[9]=_z4_t2;
     q[10]=_z4_t1;
     q[11]=_z3_t3;
     q[12]=_z3_t2;
     q[13]=_z3_t1;
     q[14]=_z2_t3;
     q[15]=_z2_t2;
     q[16]=_z2_t1;
     q[17]=_z1_t3;
     q[18]=_z1_t2;
     q[19]=_z1_t1;
     atInit = false;
     for (int i = 0; i < numMathEvents(); i++)
         if (eventFuncs[i] != NULL) eventFuncs[i]->setInit(false);
 }

 void FourZoneBuilding::der_func(const double* q, double* dq)
 {
     calc_vars(q);
     dq[0]=_DER_z1_energyUsed;
     dq[1]=_DER_z2_energyUsed;
     dq[2]=_DER_z3_energyUsed;
     dq[3]=_DER_z4_energyUsed;
     dq[4]=_DER_znoise_energyUsed;
     dq[5]=_DER_znoise_t3;
     dq[6]=_DER_znoise_t2;
     dq[7]=_DER_znoise_t1;
     dq[8]=_DER_z4_t3;
     dq[9]=_DER_z4_t2;
     dq[10]=_DER_z4_t1;
     dq[11]=_DER_z3_t3;
     dq[12]=_DER_z3_t2;
     dq[13]=_DER_z3_t1;
     dq[14]=_DER_z2_t3;
     dq[15]=_DER_z2_t2;
     dq[16]=_DER_z2_t1;
     dq[17]=_DER_z1_t3;
     dq[18]=_DER_z1_t2;
     dq[19]=_DER_z1_t1;
     dq[numVars()-1] = 1.0;
     restore_vars();
 }

 void FourZoneBuilding::postStep(double* q)
 {
     calc_vars(q);
     if (selectStateVars())
     {
         q[0] = _z1_energyUsed;
         q[1] = _z2_energyUsed;
         q[2] = _z3_energyUsed;
         q[3] = _z4_energyUsed;
         q[4] = _znoise_energyUsed;
         q[5] = _znoise_t3;
         q[6] = _znoise_t2;
         q[7] = _znoise_t1;
         q[8] = _z4_t3;
         q[9] = _z4_t2;
         q[10] = _z4_t1;
         q[11] = _z3_t3;
         q[12] = _z3_t2;
         q[13] = _z3_t1;
         q[14] = _z2_t3;
         q[15] = _z2_t2;
         q[16] = _z2_t1;
         q[17] = _z1_t3;
         q[18] = _z1_t2;
         q[19] = _z1_t1;
         calc_vars(q,true);
     }
     save_vars();
 }

 void FourZoneBuilding::save_vars()
 {
   _PRE_timeValue = timeValue;
   _PRE_z1_energyUsed=_z1_energyUsed;
   _PRE_z2_energyUsed=_z2_energyUsed;
   _PRE_z3_energyUsed=_z3_energyUsed;
   _PRE_z4_energyUsed=_z4_energyUsed;
   _PRE_znoise_energyUsed=_znoise_energyUsed;
   _PRE_znoise_t3=_znoise_t3;
   _PRE_znoise_t2=_znoise_t2;
   _PRE_znoise_t1=_znoise_t1;
   _PRE_z4_t3=_z4_t3;
   _PRE_z4_t2=_z4_t2;
   _PRE_z4_t1=_z4_t1;
   _PRE_z3_t3=_z3_t3;
   _PRE_z3_t2=_z3_t2;
   _PRE_z3_t1=_z3_t1;
   _PRE_z2_t3=_z2_t3;
   _PRE_z2_t2=_z2_t2;
   _PRE_z2_t1=_z2_t1;
   _PRE_z1_t3=_z1_t3;
   _PRE_z1_t2=_z1_t2;
   _PRE_z1_t1=_z1_t1;
   _PRE_DER_z1_energyUsed=_DER_z1_energyUsed;
   _PRE_DER_z2_energyUsed=_DER_z2_energyUsed;
   _PRE_DER_z3_energyUsed=_DER_z3_energyUsed;
   _PRE_DER_z4_energyUsed=_DER_z4_energyUsed;
   _PRE_DER_znoise_energyUsed=_DER_znoise_energyUsed;
   _PRE_DER_znoise_t3=_DER_znoise_t3;
   _PRE_DER_znoise_t2=_DER_znoise_t2;
   _PRE_DER_znoise_t1=_DER_znoise_t1;
   _PRE_DER_z4_t3=_DER_z4_t3;
   _PRE_DER_z4_t2=_DER_z4_t2;
   _PRE_DER_z4_t1=_DER_z4_t1;
   _PRE_DER_z3_t3=_DER_z3_t3;
   _PRE_DER_z3_t2=_DER_z3_t2;
   _PRE_DER_z3_t1=_DER_z3_t1;
   _PRE_DER_z2_t3=_DER_z2_t3;
   _PRE_DER_z2_t2=_DER_z2_t2;
   _PRE_DER_z2_t1=_DER_z2_t1;
   _PRE_DER_z1_t3=_DER_z1_t3;
   _PRE_DER_z1_t2=_DER_z1_t2;
   _PRE_DER_z1_t1=_DER_z1_t1;
   _PRE_link_Q[4]=_link_Q[4];
   _PRE_link_T[4]=_link_T[4];
   _PRE_link_Q[3]=_link_Q[3];
   _PRE_link_T[3]=_link_T[3];
   _PRE_link_Q[2]=_link_Q[2];
   _PRE_link_T[2]=_link_T[2];
   _PRE_link_Q[1]=_link_Q[1];
   _PRE_link_T[1]=_link_T[1];
   _PRE_link_Q[0]=_link_Q[0];
   _PRE_link_T[0]=_link_T[0];
   _PRE_outdoor_d2=_outdoor_d2;
   _PRE_outdoor_d1=_outdoor_d1;
   _PRE_outdoor_dayHour=_outdoor_dayHour;
   _PRE_outdoor_dayCycle=_outdoor_dayCycle;
   _PRE_outdoor_day=_outdoor_day;
   _PRE_z4_pin_Q=_z4_pin_Q;
   _PRE_z3_pin_Q=_z3_pin_Q;
   _PRE_z2_pin_Q=_z2_pin_Q;
   _PRE_z1_pin_Q=_z1_pin_Q;
   _PRE_z1_d3=_z1_d3;
   _PRE_z2_d3=_z2_d3;
   _PRE_z3_d3=_z3_d3;
   _PRE_z4_d3=_z4_d3;
   _PRE_znoise_d3=_znoise_d3;
   _PRE_link_pb_T[4]=_link_pb_T[4];
   _PRE_link_pb_T[2]=_link_pb_T[2];
   _PRE_link_pa_T[3]=_link_pa_T[3];
   _PRE_link_pb_T[1]=_link_pb_T[1];
   _PRE_link_pa_T[2]=_link_pa_T[2];
   _PRE_link_pb_T[0]=_link_pb_T[0];
   _PRE_link_pa_T[1]=_link_pa_T[1];
   _PRE_link_pa_T[0]=_link_pa_T[0];
   _PRE_link_pa_T[4]=_link_pa_T[4];
   _PRE_link_pb_T[3]=_link_pb_T[3];
   _PRE_link_pa_Q[4]=_link_pa_Q[4];
   _PRE_link_pb_Q[4]=_link_pb_Q[4];
   _PRE_link_pa_Q[3]=_link_pa_Q[3];
   _PRE_link_pb_Q[3]=_link_pb_Q[3];
   _PRE_link_pa_Q[2]=_link_pa_Q[2];
   _PRE_link_pb_Q[2]=_link_pb_Q[2];
   _PRE_link_pa_Q[1]=_link_pa_Q[1];
   _PRE_link_pb_Q[1]=_link_pb_Q[1];
   _PRE_link_pa_Q[0]=_link_pa_Q[0];
   _PRE_link_pb_Q[0]=_link_pb_Q[0];
   _PRE_znoise_pin_T=_znoise_pin_T;
   _PRE_z4_pin_T=_z4_pin_T;
   _PRE_z3_pin_T=_z3_pin_T;
   _PRE_z2_pin_T=_z2_pin_T;
   _PRE_z1_pin_T=_z1_pin_T;
   _PRE_znoise_d2=_znoise_d2;
   _PRE_z4_d2=_z4_d2;
   _PRE_z3_d2=_z3_d2;
   _PRE_z2_d2=_z2_d2;
   _PRE_z1_d2=_z1_d2;
   _PRE_znoise_d1=_znoise_d1;
   _PRE_z4_d1=_z4_d1;
   _PRE_z3_d1=_z3_d1;
   _PRE_z2_d1=_z2_d1;
   _PRE_z1_d1=_z1_d1;
   _PRE_znoise_dayHour=_znoise_dayHour;
   _PRE_z4_dayHour=_z4_dayHour;
   _PRE_z3_dayHour=_z3_dayHour;
   _PRE_z2_dayHour=_z2_dayHour;
   _PRE_z1_dayHour=_z1_dayHour;
   _PRE_znoise_pin_Q=_znoise_pin_Q;
   _PRE_link_KInterZone[0]=_link_KInterZone[0];
   _PRE_link_KInterZone[1]=_link_KInterZone[1];
   _PRE_link_KInterZone[2]=_link_KInterZone[2];
   _PRE_link_KInterZone[3]=_link_KInterZone[3];
   _PRE_link_KInterZone[4]=_link_KInterZone[4];
   _PRE_z1_C1=_z1_C1;
   _PRE_z1_C2=_z1_C2;
   _PRE_z1_C3=_z1_C3;
   _PRE_z1_K1=_z1_K1;
   _PRE_z1_K2=_z1_K2;
   _PRE_z1_K3=_z1_K3;
   _PRE_z1_K4=_z1_K4;
   _PRE_z1_K5=_z1_K5;
   _PRE_z1_heatHvac=_z1_heatHvac;
   _PRE_z1_coolHvac=_z1_coolHvac;
   _PRE_z2_C1=_z2_C1;
   _PRE_z2_C2=_z2_C2;
   _PRE_z2_C3=_z2_C3;
   _PRE_z2_K1=_z2_K1;
   _PRE_z2_K2=_z2_K2;
   _PRE_z2_K3=_z2_K3;
   _PRE_z2_K4=_z2_K4;
   _PRE_z2_K5=_z2_K5;
   _PRE_z2_heatHvac=_z2_heatHvac;
   _PRE_z2_coolHvac=_z2_coolHvac;
   _PRE_z3_C1=_z3_C1;
   _PRE_z3_C2=_z3_C2;
   _PRE_z3_C3=_z3_C3;
   _PRE_z3_K1=_z3_K1;
   _PRE_z3_K2=_z3_K2;
   _PRE_z3_K3=_z3_K3;
   _PRE_z3_K4=_z3_K4;
   _PRE_z3_K5=_z3_K5;
   _PRE_z3_heatHvac=_z3_heatHvac;
   _PRE_z3_coolHvac=_z3_coolHvac;
   _PRE_z4_C1=_z4_C1;
   _PRE_z4_C2=_z4_C2;
   _PRE_z4_C3=_z4_C3;
   _PRE_z4_K1=_z4_K1;
   _PRE_z4_K2=_z4_K2;
   _PRE_z4_K3=_z4_K3;
   _PRE_z4_K4=_z4_K4;
   _PRE_z4_K5=_z4_K5;
   _PRE_z4_heatHvac=_z4_heatHvac;
   _PRE_z4_coolHvac=_z4_coolHvac;
   _PRE_znoise_C1=_znoise_C1;
   _PRE_znoise_C2=_znoise_C2;
   _PRE_znoise_C3=_znoise_C3;
   _PRE_znoise_K1=_znoise_K1;
   _PRE_znoise_K2=_znoise_K2;
   _PRE_znoise_K3=_znoise_K3;
   _PRE_znoise_K4=_znoise_K4;
   _PRE_znoise_K5=_znoise_K5;
   _PRE_znoise_heatHvac=_znoise_heatHvac;
   _PRE_znoise_coolHvac=_znoise_coolHvac;
 }

 void FourZoneBuilding::restore_vars()
 {
   timeValue = _PRE_timeValue;
   _z1_energyUsed=_PRE_z1_energyUsed;
   _z2_energyUsed=_PRE_z2_energyUsed;
   _z3_energyUsed=_PRE_z3_energyUsed;
   _z4_energyUsed=_PRE_z4_energyUsed;
   _znoise_energyUsed=_PRE_znoise_energyUsed;
   _znoise_t3=_PRE_znoise_t3;
   _znoise_t2=_PRE_znoise_t2;
   _znoise_t1=_PRE_znoise_t1;
   _z4_t3=_PRE_z4_t3;
   _z4_t2=_PRE_z4_t2;
   _z4_t1=_PRE_z4_t1;
   _z3_t3=_PRE_z3_t3;
   _z3_t2=_PRE_z3_t2;
   _z3_t1=_PRE_z3_t1;
   _z2_t3=_PRE_z2_t3;
   _z2_t2=_PRE_z2_t2;
   _z2_t1=_PRE_z2_t1;
   _z1_t3=_PRE_z1_t3;
   _z1_t2=_PRE_z1_t2;
   _z1_t1=_PRE_z1_t1;
   _DER_z1_energyUsed=_PRE_DER_z1_energyUsed;
   _DER_z2_energyUsed=_PRE_DER_z2_energyUsed;
   _DER_z3_energyUsed=_PRE_DER_z3_energyUsed;
   _DER_z4_energyUsed=_PRE_DER_z4_energyUsed;
   _DER_znoise_energyUsed=_PRE_DER_znoise_energyUsed;
   _DER_znoise_t3=_PRE_DER_znoise_t3;
   _DER_znoise_t2=_PRE_DER_znoise_t2;
   _DER_znoise_t1=_PRE_DER_znoise_t1;
   _DER_z4_t3=_PRE_DER_z4_t3;
   _DER_z4_t2=_PRE_DER_z4_t2;
   _DER_z4_t1=_PRE_DER_z4_t1;
   _DER_z3_t3=_PRE_DER_z3_t3;
   _DER_z3_t2=_PRE_DER_z3_t2;
   _DER_z3_t1=_PRE_DER_z3_t1;
   _DER_z2_t3=_PRE_DER_z2_t3;
   _DER_z2_t2=_PRE_DER_z2_t2;
   _DER_z2_t1=_PRE_DER_z2_t1;
   _DER_z1_t3=_PRE_DER_z1_t3;
   _DER_z1_t2=_PRE_DER_z1_t2;
   _DER_z1_t1=_PRE_DER_z1_t1;
   _link_Q[4]=_PRE_link_Q[4];
   _link_T[4]=_PRE_link_T[4];
   _link_Q[3]=_PRE_link_Q[3];
   _link_T[3]=_PRE_link_T[3];
   _link_Q[2]=_PRE_link_Q[2];
   _link_T[2]=_PRE_link_T[2];
   _link_Q[1]=_PRE_link_Q[1];
   _link_T[1]=_PRE_link_T[1];
   _link_Q[0]=_PRE_link_Q[0];
   _link_T[0]=_PRE_link_T[0];
   _outdoor_d2=_PRE_outdoor_d2;
   _outdoor_d1=_PRE_outdoor_d1;
   _outdoor_dayHour=_PRE_outdoor_dayHour;
   _outdoor_dayCycle=_PRE_outdoor_dayCycle;
   _outdoor_day=_PRE_outdoor_day;
   _z4_pin_Q=_PRE_z4_pin_Q;
   _z3_pin_Q=_PRE_z3_pin_Q;
   _z2_pin_Q=_PRE_z2_pin_Q;
   _z1_pin_Q=_PRE_z1_pin_Q;
   _z1_d3=_PRE_z1_d3;
   _z2_d3=_PRE_z2_d3;
   _z3_d3=_PRE_z3_d3;
   _z4_d3=_PRE_z4_d3;
   _znoise_d3=_PRE_znoise_d3;
   _link_pb_T[4]=_PRE_link_pb_T[4];
   _link_pb_T[2]=_PRE_link_pb_T[2];
   _link_pa_T[3]=_PRE_link_pa_T[3];
   _link_pb_T[1]=_PRE_link_pb_T[1];
   _link_pa_T[2]=_PRE_link_pa_T[2];
   _link_pb_T[0]=_PRE_link_pb_T[0];
   _link_pa_T[1]=_PRE_link_pa_T[1];
   _link_pa_T[0]=_PRE_link_pa_T[0];
   _link_pa_T[4]=_PRE_link_pa_T[4];
   _link_pb_T[3]=_PRE_link_pb_T[3];
   _link_pa_Q[4]=_PRE_link_pa_Q[4];
   _link_pb_Q[4]=_PRE_link_pb_Q[4];
   _link_pa_Q[3]=_PRE_link_pa_Q[3];
   _link_pb_Q[3]=_PRE_link_pb_Q[3];
   _link_pa_Q[2]=_PRE_link_pa_Q[2];
   _link_pb_Q[2]=_PRE_link_pb_Q[2];
   _link_pa_Q[1]=_PRE_link_pa_Q[1];
   _link_pb_Q[1]=_PRE_link_pb_Q[1];
   _link_pa_Q[0]=_PRE_link_pa_Q[0];
   _link_pb_Q[0]=_PRE_link_pb_Q[0];
   _znoise_pin_T=_PRE_znoise_pin_T;
   _z4_pin_T=_PRE_z4_pin_T;
   _z3_pin_T=_PRE_z3_pin_T;
   _z2_pin_T=_PRE_z2_pin_T;
   _z1_pin_T=_PRE_z1_pin_T;
   _znoise_d2=_PRE_znoise_d2;
   _z4_d2=_PRE_z4_d2;
   _z3_d2=_PRE_z3_d2;
   _z2_d2=_PRE_z2_d2;
   _z1_d2=_PRE_z1_d2;
   _znoise_d1=_PRE_znoise_d1;
   _z4_d1=_PRE_z4_d1;
   _z3_d1=_PRE_z3_d1;
   _z2_d1=_PRE_z2_d1;
   _z1_d1=_PRE_z1_d1;
   _znoise_dayHour=_PRE_znoise_dayHour;
   _z4_dayHour=_PRE_z4_dayHour;
   _z3_dayHour=_PRE_z3_dayHour;
   _z2_dayHour=_PRE_z2_dayHour;
   _z1_dayHour=_PRE_z1_dayHour;
   _znoise_pin_Q=_PRE_znoise_pin_Q;
     _link_KInterZone[0]=_PRE_link_KInterZone[0];
     _link_KInterZone[1]=_PRE_link_KInterZone[1];
     _link_KInterZone[2]=_PRE_link_KInterZone[2];
     _link_KInterZone[3]=_PRE_link_KInterZone[3];
     _link_KInterZone[4]=_PRE_link_KInterZone[4];
     _z1_C1=_PRE_z1_C1;
     _z1_C2=_PRE_z1_C2;
     _z1_C3=_PRE_z1_C3;
     _z1_K1=_PRE_z1_K1;
     _z1_K2=_PRE_z1_K2;
     _z1_K3=_PRE_z1_K3;
     _z1_K4=_PRE_z1_K4;
     _z1_K5=_PRE_z1_K5;
     _z1_heatHvac=_PRE_z1_heatHvac;
     _z1_coolHvac=_PRE_z1_coolHvac;
     _z2_C1=_PRE_z2_C1;
     _z2_C2=_PRE_z2_C2;
     _z2_C3=_PRE_z2_C3;
     _z2_K1=_PRE_z2_K1;
     _z2_K2=_PRE_z2_K2;
     _z2_K3=_PRE_z2_K3;
     _z2_K4=_PRE_z2_K4;
     _z2_K5=_PRE_z2_K5;
     _z2_heatHvac=_PRE_z2_heatHvac;
     _z2_coolHvac=_PRE_z2_coolHvac;
     _z3_C1=_PRE_z3_C1;
     _z3_C2=_PRE_z3_C2;
     _z3_C3=_PRE_z3_C3;
     _z3_K1=_PRE_z3_K1;
     _z3_K2=_PRE_z3_K2;
     _z3_K3=_PRE_z3_K3;
     _z3_K4=_PRE_z3_K4;
     _z3_K5=_PRE_z3_K5;
     _z3_heatHvac=_PRE_z3_heatHvac;
     _z3_coolHvac=_PRE_z3_coolHvac;
     _z4_C1=_PRE_z4_C1;
     _z4_C2=_PRE_z4_C2;
     _z4_C3=_PRE_z4_C3;
     _z4_K1=_PRE_z4_K1;
     _z4_K2=_PRE_z4_K2;
     _z4_K3=_PRE_z4_K3;
     _z4_K4=_PRE_z4_K4;
     _z4_K5=_PRE_z4_K5;
     _z4_heatHvac=_PRE_z4_heatHvac;
     _z4_coolHvac=_PRE_z4_coolHvac;
     _znoise_C1=_PRE_znoise_C1;
     _znoise_C2=_PRE_znoise_C2;
     _znoise_C3=_PRE_znoise_C3;
     _znoise_K1=_PRE_znoise_K1;
     _znoise_K2=_PRE_znoise_K2;
     _znoise_K3=_PRE_znoise_K3;
     _znoise_K4=_PRE_znoise_K4;
     _znoise_K5=_PRE_znoise_K5;
     _znoise_heatHvac=_PRE_znoise_heatHvac;
     _znoise_coolHvac=_PRE_znoise_coolHvac;
 }

 void FourZoneBuilding::calc_vars(const double* q, bool doReinit)
 {
     bool reInit = false;
     active_model = this;
     if (atEvent || doReinit) clear_event_flags();
     // Copy state variable arrays to values used in the odes
     if (q != NULL)
     {
         timeValue = q[numVars()-1];
         _z1_energyUsed=q[0];
         _z2_energyUsed=q[1];
         _z3_energyUsed=q[2];
         _z4_energyUsed=q[3];
         _znoise_energyUsed=q[4];
         _znoise_t3=q[5];
         _znoise_t2=q[6];
         _znoise_t1=q[7];
         _z4_t3=q[8];
         _z4_t2=q[9];
         _z4_t1=q[10];
         _z3_t3=q[11];
         _z3_t2=q[12];
         _z3_t1=q[13];
         _z2_t3=q[14];
         _z2_t2=q[15];
         _z2_t1=q[16];
         _z1_t3=q[17];
         _z1_t2=q[18];
         _z1_t1=q[19];
     }
     modelica_real tmp0;
     modelica_real tmp1;
     modelica_real tmp2;
     modelica_real tmp3;
     modelica_real tmp4;
     modelica_real tmp5;
     modelica_real tmp6;
     modelica_real tmp7;
     modelica_real tmp8;
     modelica_real tmp9;
     modelica_real tmp10;
     modelica_real tmp11;
     modelica_real tmp12;
     modelica_real tmp13;
     modelica_real tmp14;
     modelica_real tmp15;
     modelica_real tmp16;
     // Primary equations
     _DER_z1_energyUsed = (fabs((((modelica_real)(modelica_integer)_z1_heatStage) * _z1_heatHvac)) + fabs((((modelica_real)(modelica_integer)_z1_coolStage) * _z1_coolHvac))); 
     _DER_z2_energyUsed = (fabs((((modelica_real)(modelica_integer)_z2_heatStage) * _z2_heatHvac)) + fabs((((modelica_real)(modelica_integer)_z2_coolStage) * _z2_coolHvac))); 
     _DER_z3_energyUsed = (fabs((((modelica_real)(modelica_integer)_z3_heatStage) * _z3_heatHvac)) + fabs((((modelica_real)(modelica_integer)_z3_coolStage) * _z3_coolHvac))); 
     _DER_z4_energyUsed = (fabs((((modelica_real)(modelica_integer)_z4_heatStage) * _z4_heatHvac)) + fabs((((modelica_real)(modelica_integer)_z4_coolStage) * _z4_coolHvac))); 
     _DER_znoise_energyUsed = (fabs((((modelica_real)(modelica_integer)_znoise_heatStage) * _znoise_heatHvac)) + fabs((((modelica_real)(modelica_integer)_znoise_coolStage) * _znoise_coolHvac))); 
     _link_T[0] = (_z1_t1 - _z2_t1); 
     _link_Q[0] = (_link_KInterZone[0] * _link_T[0]); 
     _link_T[1] = (_z2_t1 - _z3_t1); 
     _link_Q[1] = (_link_KInterZone[1] * _link_T[1]); 
     _link_T[2] = (_z3_t1 - _z4_t1); 
     _link_Q[2] = (_link_KInterZone[2] * _link_T[2]); 
     _link_T[3] = (_z4_t1 - _z1_t1); 
     _link_Q[3] = (_link_KInterZone[3] * _link_T[3]); 
     _link_T[4] = (_z1_t1 - _znoise_t1); 
     _link_Q[4] = (_link_KInterZone[4] * _link_T[4]); 
     _outdoor_day = (timeValue / 86400.0); 
     tmp0 = cos((6.28 * _outdoor_day));
     _outdoor_dayCycle = (0.5 + (tmp0 / 2.0)); 
     _outdoor_d2 = (40.0 * _outdoor_dayCycle); 
     tmp1 = DIVISION((((_znoise_K1 + _znoise_K2) * (_znoise_t1 - _znoise_t2)) + _outdoor_d2), _znoise_C2, _OMC_LIT2);
     _DER_znoise_t2 = tmp1; 
     tmp2 = DIVISION((((_z4_K1 + _z4_K2) * (_z4_t1 - _z4_t2)) + _outdoor_d2), _z4_C2, _OMC_LIT3);
     _DER_z4_t2 = tmp2; 
     tmp3 = DIVISION((((_z3_K1 + _z3_K2) * (_z3_t1 - _z3_t2)) + _outdoor_d2), _z3_C2, _OMC_LIT4);
     _DER_z3_t2 = tmp3; 
     tmp4 = DIVISION((((_z2_K1 + _z2_K2) * (_z2_t1 - _z2_t2)) + _outdoor_d2), _z2_C2, _OMC_LIT5);
     _DER_z2_t2 = tmp4; 
     tmp5 = DIVISION((((_z1_K1 + _z1_K2) * (_z1_t1 - _z1_t2)) + _outdoor_d2), _z1_C2, _OMC_LIT6);
     _DER_z1_t2 = tmp5; 
     _outdoor_d1 = (10.0 + (15.0 * _outdoor_dayCycle)); 
     tmp6 = DIVISION(((_znoise_K5 * (_znoise_t1 - _znoise_t3)) + (_znoise_K4 * (_outdoor_d1 - _znoise_t3))), _znoise_C3, _OMC_LIT7);
     _DER_znoise_t3 = tmp6; 
     tmp7 = DIVISION((((_znoise_K1 + _znoise_K2) * (_znoise_t2 - _znoise_t1)) + ((_znoise_K5 * (_znoise_t3 - _znoise_t1)) + ((_znoise_K3 * (_outdoor_d1 - _znoise_t1)) + ((((modelica_real)(modelica_integer)_znoise_heatStage) * _znoise_heatHvac) + ((((modelica_real)(modelica_integer)_znoise_coolStage) * _znoise_coolHvac) + (_outdoor_d2 + _link_Q[4])))))), _znoise_C1, _OMC_LIT8);
     _DER_znoise_t1 = tmp7; 
     tmp8 = DIVISION(((_z4_K5 * (_z4_t1 - _z4_t3)) + (_z4_K4 * (_outdoor_d1 - _z4_t3))), _z4_C3, _OMC_LIT9);
     _DER_z4_t3 = tmp8; 
     tmp9 = DIVISION(((_z3_K5 * (_z3_t1 - _z3_t3)) + (_z3_K4 * (_outdoor_d1 - _z3_t3))), _z3_C3, _OMC_LIT10);
     _DER_z3_t3 = tmp9; 
     tmp10 = DIVISION(((_z2_K5 * (_z2_t1 - _z2_t3)) + (_z2_K4 * (_outdoor_d1 - _z2_t3))), _z2_C3, _OMC_LIT11);
     _DER_z2_t3 = tmp10; 
     tmp11 = DIVISION(((_z1_K5 * (_z1_t1 - _z1_t3)) + (_z1_K4 * (_outdoor_d1 - _z1_t3))), _z1_C3, _OMC_LIT12);
     _DER_z1_t3 = tmp11; 
     tmp12 = floor(_outdoor_day, (modelica_integer) 0);
     _outdoor_dayHour = (24.0 * (_outdoor_day - tmp12)); 
     _z1_pin_Q = ((_link_Q[3] - _link_Q[4]) - _link_Q[0]); 
     tmp13 = DIVISION((((_z1_K1 + _z1_K2) * (_z1_t2 - _z1_t1)) + ((_z1_K5 * (_z1_t3 - _z1_t1)) + ((_z1_K3 * (_outdoor_d1 - _z1_t1)) + ((((modelica_real)(modelica_integer)_z1_heatStage) * _z1_heatHvac) + ((((modelica_real)(modelica_integer)_z1_coolStage) * _z1_coolHvac) + (_outdoor_d2 + _z1_pin_Q)))))), _z1_C1, _OMC_LIT13);
     _DER_z1_t1 = tmp13; 
     _z2_pin_Q = (_link_Q[0] - _link_Q[1]); 
     tmp14 = DIVISION((((_z2_K1 + _z2_K2) * (_z2_t2 - _z2_t1)) + ((_z2_K5 * (_z2_t3 - _z2_t1)) + ((_z2_K3 * (_outdoor_d1 - _z2_t1)) + ((((modelica_real)(modelica_integer)_z2_heatStage) * _z2_heatHvac) + ((((modelica_real)(modelica_integer)_z2_coolStage) * _z2_coolHvac) + (_outdoor_d2 + _z2_pin_Q)))))), _z2_C1, _OMC_LIT14);
     _DER_z2_t1 = tmp14; 
     _z3_pin_Q = (_link_Q[1] - _link_Q[2]); 
     tmp15 = DIVISION((((_z3_K1 + _z3_K2) * (_z3_t2 - _z3_t1)) + ((_z3_K5 * (_z3_t3 - _z3_t1)) + ((_z3_K3 * (_outdoor_d1 - _z3_t1)) + ((((modelica_real)(modelica_integer)_z3_heatStage) * _z3_heatHvac) + ((((modelica_real)(modelica_integer)_z3_coolStage) * _z3_coolHvac) + (_outdoor_d2 + _z3_pin_Q)))))), _z3_C1, _OMC_LIT15);
     _DER_z3_t1 = tmp15; 
     _z4_pin_Q = (_link_Q[2] - _link_Q[3]); 
     tmp16 = DIVISION((((_z4_K1 + _z4_K2) * (_z4_t2 - _z4_t1)) + ((_z4_K5 * (_z4_t3 - _z4_t1)) + ((_z4_K3 * (_outdoor_d1 - _z4_t1)) + ((((modelica_real)(modelica_integer)_z4_heatStage) * _z4_heatHvac) + ((((modelica_real)(modelica_integer)_z4_coolStage) * _z4_coolHvac) + (_outdoor_d2 + _z4_pin_Q)))))), _z4_C1, _OMC_LIT16);
     _DER_z4_t1 = tmp16; 
     // Alias equations
     // Reinits
     // Alias assignments
     _link_pb_T[4] = _znoise_t1;
     _link_pb_T[2] = _z4_t1;
     _link_pa_T[3] = _z4_t1;
     _link_pb_T[1] = _z3_t1;
     _link_pa_T[2] = _z3_t1;
     _link_pb_T[0] = _z2_t1;
     _link_pa_T[1] = _z2_t1;
     _link_pa_T[0] = _z1_t1;
     _link_pa_T[4] = _z1_t1;
     _link_pb_T[3] = _z1_t1;
     _link_pa_Q[4] = _link_Q[4];
     _link_pb_Q[4] = _link_Q[4];
     _link_pa_Q[3] = _link_Q[3];
     _link_pb_Q[3] = _link_Q[3];
     _link_pa_Q[2] = _link_Q[2];
     _link_pb_Q[2] = _link_Q[2];
     _link_pa_Q[1] = _link_Q[1];
     _link_pb_Q[1] = _link_Q[1];
     _link_pa_Q[0] = _link_Q[0];
     _link_pb_Q[0] = _link_Q[0];
     _znoise_pin_T = _znoise_t1;
     _z4_pin_T = _z4_t1;
     _z3_pin_T = _z3_t1;
     _z2_pin_T = _z2_t1;
     _z1_pin_T = _z1_t1;
     _znoise_d2 = _outdoor_d2;
     _z4_d2 = _outdoor_d2;
     _z3_d2 = _outdoor_d2;
     _z2_d2 = _outdoor_d2;
     _z1_d2 = _outdoor_d2;
     _znoise_d1 = _outdoor_d1;
     _z4_d1 = _outdoor_d1;
     _z3_d1 = _outdoor_d1;
     _z2_d1 = _outdoor_d1;
     _z1_d1 = _outdoor_d1;
     _znoise_dayHour = _outdoor_dayHour;
     _z4_dayHour = _outdoor_dayHour;
     _z3_dayHour = _outdoor_dayHour;
     _z2_dayHour = _outdoor_dayHour;
     _z1_dayHour = _outdoor_dayHour;
     _znoise_pin_Q = _link_Q[4];
     if (atEvent && !reInit) reInit = check_for_new_events();
     if (reInit)
     {
         save_vars();
         calc_vars(NULL,reInit);
     }
 }

 
 bool FourZoneBuilding::check_for_new_events()
 {
   bool result = false;
   double* z = new double[numZeroCrossings()];
     z[numRelations()+2*(modelica_integer) 0] = eventFuncs[(modelica_integer) 0]->getZUp(_outdoor_day);
     z[numRelations()+2*(modelica_integer) 0+1] = eventFuncs[(modelica_integer) 0]->getZDown(_outdoor_day);
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
 
 void FourZoneBuilding::state_event_func(const double* q, double* z)
 {
     calc_vars(q);
     z[numRelations()+2*(modelica_integer) 0] = eventFuncs[(modelica_integer) 0]->getZUp(_outdoor_day);
     z[numRelations()+2*(modelica_integer) 0+1] = eventFuncs[(modelica_integer) 0]->getZDown(_outdoor_day);
     extra_state_event_funcs(&(z[numStateEvents()]));
     restore_vars();
 }
 
 bool FourZoneBuilding::sample(int index, double tStart, double tInterval)
 {
   index--;
   assert(index >= 0);
     if (samples[index] == NULL)
         samples[index] = new AdevsSampleData(tStart,tInterval);
     return samples[index]->atEvent(timeValue,epsilon);
 }
 
 double FourZoneBuilding::time_event_func(const double* q)
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
 
 void FourZoneBuilding::internal_event(double* q, const bool* state_event)
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
     q[0]=_z1_energyUsed;
     q[1]=_z2_energyUsed;
     q[2]=_z3_energyUsed;
     q[3]=_z4_energyUsed;
     q[4]=_znoise_energyUsed;
     q[5]=_znoise_t3;
     q[6]=_znoise_t2;
     q[7]=_znoise_t1;
     q[8]=_z4_t3;
     q[9]=_z4_t2;
     q[10]=_z4_t1;
     q[11]=_z3_t3;
     q[12]=_z3_t2;
     q[13]=_z3_t1;
     q[14]=_z2_t3;
     q[15]=_z2_t2;
     q[16]=_z2_t1;
     q[17]=_z1_t3;
     q[18]=_z1_t2;
     q[19]=_z1_t1;
     for (int i = 0; i < numMathEvents(); i++)
         if (eventFuncs[i] != NULL) eventFuncs[i]->setInit(false);
     atEvent = false;
 }
 
 double FourZoneBuilding::floor(double expr, int index)
 {
     if (eventFuncs[index] == NULL)
         eventFuncs[index] = new AdevsFloorFunc(epsilon);
     return eventFuncs[index]->calcValue(expr);
 }
 
 double FourZoneBuilding::div(double x, double y, int index)
 {
     if (eventFuncs[index] == NULL)
         eventFuncs[index] = new AdevsDivFunc(epsilon);
     return eventFuncs[index]->calcValue(x/y);
 }
 
 int FourZoneBuilding::integer(double expr, int index)
 {
     if (eventFuncs[index] == NULL)
         eventFuncs[index] = new AdevsFloorFunc(epsilon);
     return int(eventFuncs[index]->calcValue(expr));
 }
 
 double FourZoneBuilding::ceil(double expr, int index)
 {
     if (eventFuncs[index] == NULL)
         eventFuncs[index] = new AdevsCeilFunc(epsilon);
     return eventFuncs[index]->calcValue(expr);
 }


 bool FourZoneBuilding::selectStateVars()
 {
     bool doReinit = false;
     return doReinit;
 }
 
 double FourZoneBuilding::calcDelay(int index, double expr, double t, double delay)
 {
     if (delays[index] == NULL || !delays[index]->isEnabled()) return expr;
     else return delays[index]->sample(t-delay);
 }
 
 void FourZoneBuilding::saveDelay(int index, double expr, double t, double max_delay)
  {
      if (delays[index] == NULL)
          delays[index] = new AdevsDelayData(max_delay);
      delays[index]->insert(t,expr);
  }
 

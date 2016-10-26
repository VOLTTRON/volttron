connector ZonePin
	Real T; // Temperature on the pin
	flow Real Q; // Heat flow through the pin
end ZonePin;

model ZoneConnector
	ZonePin pa, pb;
	Real T, Q;
	parameter Real KInterZone = 1000.0; // kW / degC
equation
	0 = pa.Q + pb.Q;
	T = pa.T - pb.T;
	Q = pa.Q;
	Q = KInterZone*T;
end ZoneConnector;

model Zone
	// Parameters
	parameter Real alpha = 1.9E-5; 
	parameter Real heatHvac = 0.008; 
	parameter Real coolHvac = -0.008; 
	input Real Tair; // outside air temperature [deg C]
	// Model variables
	ZonePin pin; // Connector for adjacent zones
	Real Troom(start=70,fixed=true); // room air temperature [deg C]
	// Input from control
	parameter Integer heatStage = 0; // 0 (off), 1, 2
	parameter Integer coolStage = 0; // 0 (off), 1, 2
	// External heating (e.g., occupants) is input from DEVS
	parameter Real delta = 0.0;

equation
	pin.T = Troom;
	der(Troom) = alpha*(Tair-Troom)+heatStage*heatHvac+coolStage*coolHvac+pin.Q+delta;
end Zone;

model ExteriorConditions
	Real day; // Current day of simulation time
	Real dayCycle; // Current part of daily period
	output Real Tair; // outside air temperature [deg C]
equation
	Tair = 68+20*dayCycle;
	day = time/(24.0*60.0*60.0);
	dayCycle = 0.5+cos(2*3.14*day)/2;
end ExteriorConditions;

model CBC
	Zone
		z1(alpha=2.8E-5),
		z2(alpha=3.5E-6),
		z3(alpha=0.033),
		z4(alpha=3.5E-6);
	ZoneConnector link[4];
	ExteriorConditions outdoor;
equation
	connect(outdoor.Tair,z1.Tair);
	connect(outdoor.Tair,z2.Tair);
	connect(outdoor.Tair,z3.Tair);
	connect(outdoor.Tair,z4.Tair);
	connect(z1.pin,link[1].pa);
	connect(z2.pin,link[2].pa);
	connect(z3.pin,link[3].pa);
	connect(z4.pin,link[4].pa);
	connect(z1.pin,link[4].pb);
	connect(z2.pin,link[1].pb);
	connect(z3.pin,link[2].pb);
	connect(z4.pin,link[3].pb);
end CBC;

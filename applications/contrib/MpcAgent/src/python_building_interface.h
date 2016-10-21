#ifndef _python_building_interface_h_
#define _python_building_interface_h_

/**
 * This is the interface for any building object, real or simulated, that
 * are contained in the ActuatorCat agent.
 */
extern "C"
{
	// Initialize the building
	void init_building();
	// Clean the building when done
	void free_building();
	// Get the number of zones
	int get_num_zones();
	// Get the temperature for a zone
	double get_indoor_temp(int zone);
	// Get the outdoor temperature
	double get_outdoor_temp();
	// Change the hvac mode for a zone. 
	// heat=1, cool=-1, off=0
	void set_hvac_mode(int zone, int mode);
	// Get the high temp limit for a zone
	double get_high_temp_limit(int zone);
	// Get the low temp limit for a zone
	double get_low_temp_limit(int zone);
	// Set the cooling and heating deadbands for a zone.
	void set_deadbands(int zone, double cool, double heat);
	// Set the fan mode. Mode 0 is auto and mode 1 is on
	void set_fan_mode(int zone, int mode);
	// Advance the clock by dt hours
	void advance(double dt_Hrs);
};

#endif

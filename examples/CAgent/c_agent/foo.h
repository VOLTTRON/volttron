#ifndef _FOO_
#define _FOO_

#define ELEMENT_ON 1
#define ELEMENT_OFF 0

#define AMBIENT_TEMP 70 /* F */

/* read only points */
int get_heating_element_status();
float get_water_temperature();

/* writable points */
int get_tgt_temperature();
void set_tgt_temperature(int);

int get_element_threshold();
void set_element_threshold(int);

#endif

#include "foo.h"

static int element_status = ELEMENT_OFF;
static int element_temp = 150;
static int target_temp = 120;
static float water_temp = AMBIENT_TEMP;
static int elem_threshold = 1;

/* Newton's Law of Cooling: dT/dt = -r (T(t) - Tambient) */
static void update_temperature() {
  float t_ambient;

  if (element_status == ELEMENT_ON)
    t_ambient = element_temp;
  else
    t_ambient = AMBIENT_TEMP;


  water_temp += (0.05) * (t_ambient - water_temp);
}

static void update_element() {
  if (water_temp >= target_temp + elem_threshold) {
    element_status = ELEMENT_OFF;
  }
  else if (water_temp <= target_temp - elem_threshold) {
    element_status = ELEMENT_ON;
  }
}

int get_heating_element_status() {
  return element_status;
}

float get_water_temperature() {
  update_temperature();
  update_element();

  return water_temp;
}

int get_tgt_temperature() {
  return target_temp;
}

void set_tgt_temperature(int temp) {
  target_temp = temp;
}

int get_element_threshold() {
  return elem_threshold;
}

void set_element_threshold(int t) {
  elem_threshold = t;
}

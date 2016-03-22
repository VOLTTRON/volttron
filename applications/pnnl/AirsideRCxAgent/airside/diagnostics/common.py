import datetime
from datetime import timedelta as td


def check_date(current_time, timestamp_array):
    '''Check current timestamp with previous timestamp

    to verify that there are no large missing data gaps.
    '''
    if not timestamp_array:
        return False
    if current_time.date() != timestamp_array[-1].date():
        if (timestamp_array[-1].date() + td(days=1) != current_time.date() or
                (timestamp_array[-1].hour != 23 and current_time.hour == 0)):
            return True
        return False


def validation_builder(validate, dx_name, data_tag):
    data = {}
    for key, value in validate.items():
        tag = dx_name + data_tag + key
        data.update({tag: value})
    return data


def check_run_status(timestamp_array, current_time, no_required_data):
    if timestamp_array and timestamp_array[-1].hour != current_time.hour:
        if len(timestamp_array) < no_required_data:
            return None
        return True
    return False


def setpoint_control_check(setpoint_array, point_array, allowable_deviation,
                           dx_name, dx_tag):
    """Verify that point is tracking well with set point."""
    average_setpoint = None
    setpoint_array = [float(pt) for pt in setpoint_array if pt !=0]
    if setpoint_array:
        average_setpoint = sum(setpoint_array)/len(setpoint_array)
        zipper = (setpoint_array, point_array)
        stpt_tracking = [abs(x - y) for x, y in zip(*zipper)]
        stpt_tracking = (sum(stpt_tracking)/len(stpt_tracking))/average_setpoint*100

        if stpt_tracking > allowable_deviation:
            # color_code = 'red'
            msg = ('Supply-air temperature is deviating significantly '
                   'from the supply-air temperature set point.')
            dx_msg = 31.1
            dx_table = {dx_name + dx_tag: dx_msg}
        else:
            # color_code = 'green'
            msg = 'No problem detected.'
            dx_msg = 30.0
            dx_table = {dx_name + dx_tag: dx_msg}
    else:
        # color_code = 'grey'
        msg = ('Supply-air temperature set point data is not available. '
               'The Supply-air Temperature Set Point Control Loop '
               'Diagnostic required supply-air temperature set point '
               'data.')
        dx_msg = 32.2
        dx_table = {dx_name + dx_tag: dx_msg}
    return average_setpoint, msg, dx_table
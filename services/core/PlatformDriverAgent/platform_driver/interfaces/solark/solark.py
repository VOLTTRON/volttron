# -*- coding: utf-8 -*-
"""
Created on Tue Sep 12 17:57:03 2023

@author: wendell

Modified by cristian@aceiotsolutions.com

"""
import logging
import grequests

_log = logging.getLogger("solarklib")

def _grequests_exception_handler(request, exception):
    trace = exception.__traceback__
    _log.error(f"grequests error: {exception}: {trace.tb_frame.f_code.co_filename}:{trace.tb_lineno}")

#%% HTTP functions
def user_exists(username):
    """
    Check if a user exists in the database.

    Args:
    - username (str): The username to check.

    Returns:
    - bool: True if the user exists, False otherwise.
    """
    # Make a request to the database to check if the user exists
    url = f'https://openapi.mysolark.com/v1/anonymous/checkAccount'
    request = grequests.get(url, params={'username': username})
    result = grequests.map([request])[0]
    return result.json()

# 3.1 Get Token ( bearer)
def fetch_bearer_token(key, username, password, grant_type="password", client_id="csp-web"):
    """
    Fetches the bearer token using provided credentials.

    Args:
    - key (str): The API key for the request.
    - username (str): The username for authentication.
    - password (str): The password for authentication.
    - grant_type (str, optional): The grant type for OAuth. Defaults to 'password'.
    - client_id (str, optional): The client ID. Defaults to 'csp-web'.

    Returns:
    - str: The bearer token.
    """
    # URL and headers
    url = 'https://openapi.mysolark.com/v1/oauth/token'
    headers = {
        'x-api-key': key,
        'Content-Type': 'application/json',
    }

    # Request body data
    data = {
        "username": username,
        "password": password,
        "grant_type": grant_type,
        "client_id": client_id
    }

    request = grequests.post(url, headers=headers, json=data)
    result = grequests.map([request], exception_handler=_grequests_exception_handler)[0]

    # Check if response was successful and is JSON
    if result.status_code == 200 and 'application/json' in result.headers['Content-Type']:
        token_data = result.json()
        return 'Bearer ' + token_data['data']['access_token']
    else:
        _log.error("Error fetching bearer token")
        _log.debug(result.status_code)
        _log.debug(result.text)
        return None




# 3.2.1 Get Plant List
def get_plant_list(key, bearer, page=1, limit=20):
    """
    Fetches a list of plants.

    Args:
    - key (str): The API key for the request.
    - bearer (str): The bearer token for authorization.
    - page (int, optional): The page number for pagination. Defaults to 1.
    - limit (int, optional): The number of results per page. Defaults to 20.

    Returns:
    - dict: A dictionary containing plant data.
    """
    # Construct the URL with page and limit parameters
    url = f'https://openapi.mysolark.com/v1/plants?page={page}&limit={limit}'

    # Set up the headers
    headers = {
        'x-api-key': key,
        'Content-Type': 'application/json',
        'Authorization': bearer
    }

    # Make the GET request
    request = grequests.get(url, headers=headers)
    result = grequests.map([request])[0]

    # Check the response
    if result.status_code == 200 and 'application/json' in result.headers['Content-Type']:
        return result.json()['data']['infos']
    else:
        _log.error("Error fetching plant list")
        _log.debug(result.status_code)
        _log.debug(result.text)
        return None



# 3.2.3 Get plant realtime 
# Get plant realtime Photovoltaic (PV) energy production over various intervals.
def get_plant_realtime(plant_id, key, bearer):
    # Construct the URL using the given plant_id
    url = f'https://openapi.mysolark.com/v1/plant/{plant_id}/realtime'

    # Set up the headers using the given key and bearer
    headers = {
        'x-api-key': key,
        'Content-Type': 'application/json',
        'Authorization': bearer
    }

    # Make the GET request
    request = grequests.get(url, headers=headers)
    result = grequests.map([request])[0]

    # Return the response in case you want to process it further
    if result.status_code == 200 and 'application/json' in result.headers['Content-Type']:
        return result.json()['data']
    else:
        _log.error("Error fetching plant realtime data")
        _log.debug(result.status_code)
        _log.debug(result.text)
        return None



# 3.2.4 Get plant flow
def get_plant_flow(plant_id, key, bearer):
    """
    Fetches the flow data for a specific plant.

    Args:
    - plant_id (int): The ID of the plant for which the flow data is needed.
    - key (str): The API key for the request.
    - bearer (str): The bearer token for authorization.

    Returns:
    - dict: A dictionary containing plant flow data.
    """
    # Construct the URL using the given plant_id
    url = f'https://openapi.mysolark.com/v1/plant/energy/{plant_id}/flow'

    # Set up the headers using the given key and bearer
    headers = {
        'x-api-key': key,
        'Content-Type': 'application/json',
        'Authorization': bearer
    }

    # Make the GET request
    request = grequests.get(url, headers=headers)
    result = grequests.map([request])[0]

    # Check the response
    if result.status_code == 200 and 'application/json' in result.headers['Content-Type']:
        return result.json()['data']
    else:
        _log.error("Error fetching plant flow data")
        _log.debug(result.status_code)
        _log.debug(result.text)
        return None


    

# 3.2.7 Get energy day chart
def get_energy_day_chart(plant_id, date, key, bearer, lan="en"):
    """
    Fetches the energy day chart data for a specific plant on a specific date.

    Args:
    - plant_id (int): The ID of the plant for which the data is needed.
    - date (str): The date for which the energy data is required in the format 'YYYY-MM-DD'.
    - key (str): The API key for the request.
    - bearer (str): The bearer token for authorization.
    - lan (str, optional): The language parameter. Defaults to 'en'.

    Returns:
    - dict: A dictionary containing the energy day chart data.
    """
    
    # Construct the URL using the given plant_id and date
    url = f'https://openapi.mysolark.com/v1/plant/energy/{plant_id}/day?date={date}&lan={lan}'

    # Set up the headers using the given key and bearer
    headers = {
        'x-api-key': key,
        'Content-Type': 'application/json',
        'Authorization': bearer
    }

    # Make the GET request
    request = grequests.get(url, headers=headers)
    result = grequests.map([request])[0]

    # Check the response
    if result.status_code == 200 and 'application/json' in result.headers['Content-Type']:
        return result.json()
    else:
        _log.error("Error fetching energy day chart data")
        _log.debug(result.status_code)
        _log.debug(result.text)
        return None
    
    
# 4.1 Get param setting
def get_param_settings(sn_inverter, key, bearer):
    """
    Get Inverter Parameters Settings

    Args:
    - sn_inverter (int): The serie number (SN) for the Inverter 
    - key (str): The API key for the request.
    - bearer (str): The bearer token for authorization.

    Returns:
    - dict: A dictionary containing the energy day chart data.
    """
    url = f'https://openapi.mysolark.com/v1/dy/store/{sn_inverter}/read'

    headers = {
        "x-api-key": key,
        "Content-Type": "application/json",
        "Authorization": bearer
    }

    request = grequests.get(url, headers=headers)
    result = grequests.map([request])[0]

    if result.status_code == 200:
        return result.json()['data']
    else:
        result.raise_for_status()  # This will raise an error if the HTTP status code is not 200

# 4.2 Work model setting
def set_param_settings(key, bearer, sn_inverter, data):
    url = f"https://mysolark.com:443/api/v1/dy/store/{sn_inverter}/setting/workMode"

    headers = {
        "Authorization": bearer,
        "x-api-key": key,
        "Content-Type": "application/json"
    }

    request = grequests.post(url, headers=headers, json=data)
    result = grequests.map([request])[0]

    if result.status_code == 200:
        return result.json()
    else:
        result.raise_for_status()  # This will raise an error if the HTTP status code is not 200


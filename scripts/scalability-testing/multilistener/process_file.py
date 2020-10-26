#!/usr/local/bin/python3

import argparse
import json

import numpy

def load_data(file_path):
    data = None
    with open(file_path, 'r') as input_file:
        data = json.load(input_file)
    return data

def pivot_data(data):
    result = {}
    for agent,agent_results in data.items():
        result[agent] = []
        for an_index,full_scrape in enumerate(agent_results):
            result[agent].append({})
            result[agent][an_index] = {
                'header_times': numpy.array([device['header_t'] for device in full_scrape]),
                'client_times': numpy.array([device['client_t'] for device in full_scrape]),
            }
    return result

def main(input):
    raw_data = load_data(input)
    pivoted_data = pivot_data(raw_data)

    # average over agents and publishes of the full time of each publish
    overall_result = {}
    for agent,agent_results in raw_data.items():
        for devices in agent_results:
            #scrape_times = [i_device['client_t'][-1] - i_device['header_t'][0] for i_device in device]
            scrape_time = devices[-1]['client_t'] - devices[0]['header_t']
            overall_result[agent] = {
                'total_time': scrape_time,
                'time_per_device': scrape_time/len(devices)
            }
    mean_over_agents = numpy.mean([data['total_time'] for agent,data in overall_result.items()])
    norm_mean_over_agents = numpy.mean([data['time_per_device'] for agent,data in overall_result.items()])
    print(f'full mean time: [{mean_over_agents:.4f}] sec. ({norm_mean_over_agents:.4f} sec./device)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', action='store', type=str, required=True)
    options = parser.parse_args()

    main(options.input)

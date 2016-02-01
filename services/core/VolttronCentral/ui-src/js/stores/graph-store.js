'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');


var graphStore = new Store();

graphStore.getGraphs = function (uuid) {
    

    return null;
};

graphStore.getLastError = function (uuid) {
    return _lastErrors[uuid] || null;
};

graphStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    
});

graphStore.getGraphData = function () {
    var graphJson = [
  {
    "year": 2011,
    "month": 1,
    "avg_max_temp_f": 46.83,
    "avg_min_temp_f": 28.1,
    "avg_temp_f": 37.47,
    "total_percipitation_in": 2.35,
    "total_snowfall_in": 9.6
  },
  {
    "year": 2011,
    "month": 2,
    "avg_max_temp_f": 47.58,
    "avg_min_temp_f": 26.35,
    "avg_temp_f": 36.96,
    "total_percipitation_in": 7.61,
    "total_snowfall_in": 25.5
  },
  {
    "year": 2011,
    "month": 3,
    "avg_max_temp_f": 51.45,
    "avg_min_temp_f": 31.39,
    "avg_temp_f": 41.42,
    "total_percipitation_in": 11.74,
    "total_snowfall_in": 39.6
  },
  {
    "year": 2011,
    "month": 4,
    "avg_max_temp_f": 61.5,
    "avg_min_temp_f": 35.13,
    "avg_temp_f": 48.32,
    "total_percipitation_in": 1.44,
    "total_snowfall_in": 2.3
  },
  {
    "year": 2011,
    "month": 5,
    "avg_max_temp_f": 64.9,
    "avg_min_temp_f": 40.68,
    "avg_temp_f": 52.79,
    "total_percipitation_in": 2.17,
    "total_snowfall_in": 0
  },
  {
    "year": 2011,
    "month": 6,
    "avg_max_temp_f": 73.79,
    "avg_min_temp_f": 48.18,
    "avg_temp_f": 60.98,
    "total_percipitation_in": 2.06,
    "total_snowfall_in": 0
  },
  {
    "year": 2011,
    "month": 7,
    "avg_max_temp_f": 85.07,
    "avg_min_temp_f": 56.1,
    "avg_temp_f": 70.58,
    "total_percipitation_in": 0,
    "total_snowfall_in": 0
  },
  {
    "year": 2011,
    "month": 8,
    "avg_max_temp_f": 88.1,
    "avg_min_temp_f": 56.45,
    "avg_temp_f": 72.28,
    "total_percipitation_in": 0.15,
    "total_snowfall_in": 0
  },
  {
    "year": 2011,
    "month": 9,
    "avg_max_temp_f": 84.47,
    "avg_min_temp_f": 54.13,
    "avg_temp_f": 69.3,
    "total_percipitation_in": 3.42,
    "total_snowfall_in": 0
  },
  {
    "year": 2011,
    "month": 10,
    "avg_max_temp_f": 71.14,
    "avg_min_temp_f": 43.54,
    "avg_temp_f": 57.34,
    "total_percipitation_in": 2.8,
    "total_snowfall_in": 0
  },
  {
    "year": 2011,
    "month": 11,
    "avg_max_temp_f": 53.62,
    "avg_min_temp_f": 32.07,
    "avg_temp_f": 42.62,
    "total_percipitation_in": 1.07,
    "total_snowfall_in": 5
  },
  {
    "year": 2011,
    "month": 12,
    "avg_max_temp_f": 48.97,
    "avg_min_temp_f": 25.42,
    "avg_temp_f": 37.19,
    "total_percipitation_in": 0,
    "total_snowfall_in": 0
  },
  {
    "year": 2012,
    "month": 1,
    "avg_max_temp_f": 51.5,
    "avg_min_temp_f": 28.2,
    "avg_temp_f": 39.85,
    "total_percipitation_in": 4.98,
    "total_snowfall_in": 1.1
  },
  {
    "year": 2012,
    "month": 2,
    "avg_max_temp_f": 54.32,
    "avg_min_temp_f": 29.86,
    "avg_temp_f": 42.09,
    "total_percipitation_in": 0.9,
    "total_snowfall_in": 11
  },
  {
    "year": 2012,
    "month": 3,
    "avg_max_temp_f": 54.45,
    "avg_min_temp_f": 32.62,
    "avg_temp_f": 43.53,
    "total_percipitation_in": 5.76,
    "total_snowfall_in": 24.5
  },
  {
    "year": 2012,
    "month": 4,
    "avg_max_temp_f": 63.69,
    "avg_min_temp_f": 38.83,
    "avg_temp_f": 51.12,
    "total_percipitation_in": 4.45,
    "total_snowfall_in": 5.5
  },
  {
    "year": 2012,
    "month": 5,
    "avg_max_temp_f": 75.45,
    "avg_min_temp_f": 46.57,
    "avg_temp_f": 61.16,
    "total_percipitation_in": 0.33,
    "total_snowfall_in": 0
  },
  {
    "year": 2012,
    "month": 6,
    "avg_max_temp_f": 82.21,
    "avg_min_temp_f": 51.36,
    "avg_temp_f": 66.79,
    "total_percipitation_in": 0.67,
    "total_snowfall_in": 0
  },
  {
    "year": 2012,
    "month": 7,
    "avg_max_temp_f": 89.3,
    "avg_min_temp_f": 57.4,
    "avg_temp_f": 73.35,
    "total_percipitation_in": 0.01,
    "total_snowfall_in": 0
  },
  {
    "year": 2012,
    "month": 8,
    "avg_max_temp_f": 93.14,
    "avg_min_temp_f": 60.62,
    "avg_temp_f": 76.88,
    "total_percipitation_in": 0.06,
    "total_snowfall_in": 0
  },
  {
    "year": 2012,
    "month": 9,
    "avg_max_temp_f": 87.41,
    "avg_min_temp_f": 56.1,
    "avg_temp_f": 71.76,
    "total_percipitation_in": 0,
    "total_snowfall_in": 0
  },
  {
    "year": 2012,
    "month": 10,
    "avg_max_temp_f": 72.04,
    "avg_min_temp_f": 44.89,
    "avg_temp_f": 58.46,
    "total_percipitation_in": 1.47,
    "total_snowfall_in": 0
  },
  {
    "year": 2012,
    "month": 11,
    "avg_max_temp_f": 56.04,
    "avg_min_temp_f": 35.39,
    "avg_temp_f": 45.71,
    "total_percipitation_in": 5.06,
    "total_snowfall_in": 6.5
  },
  {
    "year": 2012,
    "month": 12,
    "avg_max_temp_f": 42.64,
    "avg_min_temp_f": 29.93,
    "avg_temp_f": 36.29,
    "total_percipitation_in": 11.91,
    "total_snowfall_in": 18.5
  },
  {
    "year": 2013,
    "month": 1,
    "avg_max_temp_f": 44.25,
    "avg_min_temp_f": 23.25,
    "avg_temp_f": 33.75,
    "total_percipitation_in": 0.91,
    "total_snowfall_in": 2
  },
  {
    "year": 2013,
    "month": 2,
    "avg_max_temp_f": 53.14,
    "avg_min_temp_f": 27.9,
    "avg_temp_f": 40.52,
    "total_percipitation_in": 0.5,
    "total_snowfall_in": 1.1
  },
  {
    "year": 2013,
    "month": 3,
    "avg_max_temp_f": 61.18,
    "avg_min_temp_f": 36.18,
    "avg_temp_f": 48.68,
    "total_percipitation_in": 2.99,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 4,
    "avg_max_temp_f": 67.76,
    "avg_min_temp_f": 41.24,
    "avg_temp_f": 54.5,
    "total_percipitation_in": 1.64,
    "total_snowfall_in": 0.5
  },
  {
    "year": 2013,
    "month": 5,
    "avg_max_temp_f": 73.55,
    "avg_min_temp_f": 47.86,
    "avg_temp_f": 60.7,
    "total_percipitation_in": 2.96,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 6,
    "avg_max_temp_f": 84.77,
    "avg_min_temp_f": 55.1,
    "avg_temp_f": 69.93,
    "total_percipitation_in": 0.16,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 7,
    "avg_max_temp_f": 93.69,
    "avg_min_temp_f": 61.81,
    "avg_temp_f": 77.75,
    "total_percipitation_in": 0.02,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 8,
    "avg_max_temp_f": 89.25,
    "avg_min_temp_f": 55.89,
    "avg_temp_f": 72.57,
    "total_percipitation_in": 0,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 9,
    "avg_max_temp_f": 82,
    "avg_min_temp_f": 50.78,
    "avg_temp_f": 66.39,
    "total_percipitation_in": 0.92,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 10,
    "avg_max_temp_f": 69.5,
    "avg_min_temp_f": 39.5,
    "avg_temp_f": 54.5,
    "total_percipitation_in": 0.94,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 11,
    "avg_max_temp_f": 60.32,
    "avg_min_temp_f": 33.63,
    "avg_temp_f": 46.97,
    "total_percipitation_in": 0.73,
    "total_snowfall_in": 0
  },
  {
    "year": 2013,
    "month": 12,
    "avg_max_temp_f": 48.81,
    "avg_min_temp_f": 24.95,
    "avg_temp_f": 36.88,
    "total_percipitation_in": 1.53,
    "total_snowfall_in": 10.5
  },
  {
    "year": 2014,
    "month": 1,
    "avg_max_temp_f": 57.13,
    "avg_min_temp_f": 31.32,
    "avg_temp_f": 44.23,
    "total_percipitation_in": 1.01,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 2,
    "avg_max_temp_f": 54.64,
    "avg_min_temp_f": 34.82,
    "avg_temp_f": 44.73,
    "total_percipitation_in": 5.47,
    "total_snowfall_in": 2
  },
  {
    "year": 2014,
    "month": 3,
    "avg_max_temp_f": 62.48,
    "avg_min_temp_f": 37.44,
    "avg_temp_f": 49.96,
    "total_percipitation_in": 3.89,
    "total_snowfall_in": 1
  },
  {
    "year": 2014,
    "month": 4,
    "avg_max_temp_f": 66.56,
    "avg_min_temp_f": 40.5,
    "avg_temp_f": 53.53,
    "total_percipitation_in": 2.81,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 5,
    "avg_max_temp_f": 75.83,
    "avg_min_temp_f": 46.83,
    "avg_temp_f": 61.33,
    "total_percipitation_in": 0.73,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 6,
    "avg_max_temp_f": 85.28,
    "avg_min_temp_f": 53.39,
    "avg_temp_f": 69.33,
    "total_percipitation_in": 0.2,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 7,
    "avg_max_temp_f": 91,
    "avg_min_temp_f": 60.93,
    "avg_temp_f": 75.97,
    "total_percipitation_in": 0.28,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 8,
    "avg_max_temp_f": 88.85,
    "avg_min_temp_f": 57.8,
    "avg_temp_f": 73.33,
    "total_percipitation_in": 0.15,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 9,
    "avg_max_temp_f": 85.04,
    "avg_min_temp_f": 53.5,
    "avg_temp_f": 69.27,
    "total_percipitation_in": 0.54,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 10,
    "avg_max_temp_f": 76.79,
    "avg_min_temp_f": 36.18,
    "avg_temp_f": 56.48,
    "total_percipitation_in": 0,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 11,
    "avg_max_temp_f": 59.27,
    "avg_min_temp_f": 33.53,
    "avg_temp_f": 46.4,
    "total_percipitation_in": 2.98,
    "total_snowfall_in": 0
  },
  {
    "year": 2014,
    "month": 12,
    "avg_max_temp_f": 48.86,
    "avg_min_temp_f": 32.79,
    "avg_temp_f": 40.82,
    "total_percipitation_in": 4.71,
    "total_snowfall_in": 1.2
  },
  {
    "year": 2015,
    "month": 1,
    "avg_max_temp_f": 56.96,
    "avg_min_temp_f": 30.39,
    "avg_temp_f": 43.68,
    "total_percipitation_in": 0.1,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 2,
    "avg_max_temp_f": 64.82,
    "avg_min_temp_f": 36,
    "avg_temp_f": 50.3,
    "total_percipitation_in": 1.63,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 3,
    "avg_max_temp_f": 67.29,
    "avg_min_temp_f": 38.33,
    "avg_temp_f": 52.81,
    "total_percipitation_in": 0.43,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 4,
    "avg_max_temp_f": 66.35,
    "avg_min_temp_f": 37.73,
    "avg_temp_f": 52.04,
    "total_percipitation_in": 3.15,
    "total_snowfall_in": 4.5
  },
  {
    "year": 2015,
    "month": 5,
    "avg_max_temp_f": 68.81,
    "avg_min_temp_f": 43.96,
    "avg_temp_f": 56.38,
    "total_percipitation_in": 1.97,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 6,
    "avg_max_temp_f": 87.97,
    "avg_min_temp_f": 57.23,
    "avg_temp_f": 72.6,
    "total_percipitation_in": 0.79,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 7,
    "avg_max_temp_f": 87.68,
    "avg_min_temp_f": 59.71,
    "avg_temp_f": 73.69,
    "total_percipitation_in": 2.58,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 8,
    "avg_max_temp_f": 91.39,
    "avg_min_temp_f": 58.68,
    "avg_temp_f": 75.03,
    "total_percipitation_in": 0.04,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 9,
    "avg_max_temp_f": 85.07,
    "avg_min_temp_f": 55.86,
    "avg_temp_f": 70.41,
    "total_percipitation_in": 0.15,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 10,
    "avg_max_temp_f": 73.26,
    "avg_min_temp_f": 46.17,
    "avg_temp_f": 59.93,
    "total_percipitation_in": 3.37,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 11,
    "avg_max_temp_f": 50.5,
    "avg_min_temp_f": 29.36,
    "avg_temp_f": 39.93,
    "total_percipitation_in": 3.74,
    "total_snowfall_in": 0
  },
  {
    "year": 2015,
    "month": 12,
    "avg_max_temp_f": 43.42,
    "avg_min_temp_f": 24.65,
    "avg_temp_f": 34.03,
    "total_percipitation_in": 5.18,
    "total_snowfall_in": 0
  }
];

    return graphJson;
};


module.exports = graphStore;

'use strict';

var CsvParse = require('babyparse');

var parseCsvFile = (contents) => {

    var results = CsvParse.parse(contents);

    var registryValues = [];

    var header = [];

    var data = results.data;

    results.warnings = [];

    if (data.length)
    {
        header = data.slice(0, 1);
    }

    var template = [];

    if (header[0].length)
    {
        header[0].forEach(function (column) {
            template.push({ "key": column.replace(/ /g, "_"), "value": null, "label": column });
        });

        var templateLength = template.length;

        if (data.length > 1)
        {
            var rows = data.slice(1);

            var rowsCount = rows.length;

            rows.forEach(function (r, num) {

                if (r.length)
                {   
                    if (r.length !== templateLength) 
                    {                           
                        if ((num === (rowsCount - 1)) && (r.length === 0 || ((r.length === 1) && (r[0] === "") )))
                        {
                            // Suppress the warning message if the out-of-sync row is the last one and it has no elements
                            // or all it has is an empty point name -- which can happen naturally when reading the csv file
                        }
                        else
                        {
                            results.warnings.push({ message: "Row " +  num + " was omitted for having the wrong number of columns."});
                        }
                    }
                    else
                    {
                        if (r.length === templateLength) // Have to check again, to keep from adding the empty point name
                        {                                // in the last row
                            var newTemplate = JSON.parse(JSON.stringify(template));

                            var newRow = [];

                            r.forEach( function (value, i) {
                                newTemplate[i].value = value;

                                newRow.push(newTemplate[i]);
                            });

                            registryValues.push(newRow);
                        }
                    }
                }
            });
        }
        else
        {
            registryValues = template;
        }
    }

    results.data = registryValues;

    return results;
}

export default { parseCsvFile };

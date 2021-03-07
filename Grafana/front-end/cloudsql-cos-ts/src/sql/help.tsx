//# ------------------------------------------------------------------------------
//# Copyright IBM Corp. 2020
//#
//# Licensed under the Apache License, Version 2.0 (the "License");
//# you may not use this file except in compliance with the License.
//# You may obtain a copy of the License at
//#
//#    http://www.apache.org/licenses/LICENSE-2.0
//#
//# Unless required by applicable law or agreed to in writing, software
//# distributed under the License is distributed on an "AS IS" BASIS,
//# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//# See the License for the specific language governing permissions and
//# limitations under the License.
//# ------------------------------------------------------------------------------
/* eslint-disable */
import React, { PureComponent } from 'react';
//import { readFileSync } from 'fs';

// tslint:disable-block
/* tslint:disable */
export class CloudSQLHelp extends PureComponent {
  render() {
    //const data = readFileSync('./help_sql.txt', { encoding: 'utf-8', flag: 'r' });
    //var myTxt = require('./help_sql.txt');
    return (
      <>
        <div className="gf-form-group">
          <div className="gf-form">
            {/*<pre className="gf-form-pre">{data}</pre>*/}
            <pre className="gf-form-pre alert alert-info">
<b>Time series</b>
<br/>

            - return column named time (in UTC), as a unix time stamp or any sql native date data type. You can use the macros below.
            <br/>
 - any other columns returned will be the time point values.
            <br/>
 Optional:
            <br/>
   - return column named <i>metric</i> to represent the series name.
            <br/>
   - If multiple value columns are returned the metric column is used as prefix.
            <br/>
   - If no column named metric is found the column name of the value column is used as series name
            <br/>

 Resultsets of time series queries need to be sorted by time.
            <br/>
            <br/>
            <br/>
<b>Table</b>:
<br/>
- return any set of columns
<br/>

<br/>
<b><a href='https://grafana.com/docs/grafana/latest/variables/'>Variables</a></b>:
<br/>
- $&#123;variable_name&#125; - &gt; in the dashboard's setting, you select 'Variables' and create a new one with the name `variable_name` (with values can be user-input or retrieved as a result of a CloudSQL Query), then you can reference to the selected value in the query using the above syntax: dollar sign, open curly brance, name and closing curly brace.
<br/>
  NOTE: For string-value, put that into the double-quote, i.e. "$&#123;variable_name&#125;"
<br/>

<br/>
<b>Macros</b>:
<br/>
- $__source  -&gt; the datasource as provided in DataSource setting
<br/>
- $__source_test -&gt; the fake time-series datasource, e.g. $__source_test(TS) or $__source_test(MTS)
<br/>
- $__dest[(format [,suffix])] -&gt; the location to store data as provided in DataSource setting, e.g. $__dest, $__dest(), $__dest(csv), $__dest(CSV), $__dest(parquet, a/b/c)
<br/>
Example you want to save queried data to the TARGET_COS_URL with suffix 'a/b/c' in the format 'PARQUET:
<br/>
SELECT * FROM $__source INTO $__dest(parquet, a/b/c)
<br/>
<br/>
  - $__source_prev -&gt; reference to the output from a previous query in the same dashboard/panel, e.g. $__source_prev(A)
<br/>
- $__timeFilter() -&gt; time_column BETWEEN '2017-04-21T05:01:17Z' AND '2017-04-21T05:01:17Z'
- $__timeFilterColumn(column-name, [type]) -&gt; add time filter using the given column name (1st argument), and its type (2nd argument)
<br/>

<br/>
<b>Cloud SQL:</b>
<br/>
DISTRIBUTE BY, SORT BY and CLUSTER BY only have an effect during your SQL query execution and do not influence the query result written back to Cloud Object Storage. Use these clauses only in execution of subqueries in order to optimize the outer query execution that works on the intermediate result sets produced by the sub queries.
<br/>
            </pre>
          </div>
        </div>
      </>
    );
  }
}

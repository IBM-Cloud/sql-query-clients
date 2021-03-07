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
import { DataQuery, DataSourceJsonData, SelectableValue } from "@grafana/data";

export const FORMAT_OPTIONS: Array<SelectableValue<string>> = [
  { label: "Time series", value: "time_series" },
  { label: "Table", value: "table" },
];

export interface CloudSQLQuery extends DataQuery {
  queryText?: string; // sql_stmt?: string;

  id?: number; //track the ID of the associated datasource instance
  name?: string; //track the name of the associated datasource instance
  format: string; //'timeseries' or something else?
  time_column?: string;
  metrics_column?: string; //the column from which uniques values represent different metrics
  get_result: boolean; // default is checked, i.e. the queried data is also returned
  showingHelp: boolean;
}

export const defaultTSQuery: Partial<CloudSQLQuery> = {
  //return single time-series
  queryText: `WITH container_ts_table AS
  (SELECT field_name,
          ts
   FROM <COS_IN_URL> STORED AS PARQUET USING TIME_SERIES_FORMAT(KEY="field_name", timetick="time_stamp", value="observation") IN ts),
 tmp_table AS
(
SELECT field_name AS user_agent,
       ts_explode(ts_seg_sum(TS_SEGMENT_BY_TIME(ts, 604800000, 604800000))) AS (tt,
                                                                                value)
FROM container_ts_table)
 SELECT tt, log(value) as value
FROM tmp_table
WHERE user_agent LIKE "COS GO"
INTO <COS_OUT_URL> STORED AS PARQUET`,
  format: "time_series",
  time_column: "tt",
};
export const defaultMTSQuery: Partial<CloudSQLQuery> = {
  //return multiple time-series
  queryText: `WITH container_ts_table AS
  (SELECT field_name,
          ts
   FROM <COS_IN_URL> STORED AS PARQUET USING TIME_SERIES_FORMAT(KEY="field_name", timetick="time_stamp", value="observation") IN ts),
 tmp_table AS
(
SELECT
       ts_explode(ts_seg_sum(TS_SEGMENT_BY_TIME(ts, 604800000, 604800000))) AS (tt,
                                                                                value), field_name AS user_agent
FROM container_ts_table)
 SELECT tt, log(value) as value, user_agent
FROM tmp_table
INTO <COS_OUT_URL> STORED AS PARQUET`,
  format: "time_series",
  time_column: "tt",
  metrics_column: "user_agent",
};
export const defaultQuery: Partial<CloudSQLQuery> = {
  queryText: `WITH container_ts_table AS
  (SELECT field_name,
          ts
   FROM <COS_IN_URL> STORED AS PARQUET USING TIME_SERIES_FORMAT(KEY="field_name", timetick="time_stamp", value="observation") IN ts)
SELECT field_name AS user_agent,
       ts_explode(ts_seg_sum(TS_SEGMENT_BY_TIME(ts, 604800000, 604800000))) AS (tt,
                                                                                value)
FROM container_ts_table INTO <COS_OUT_URL> STORED AS PARQUET`,
  format: "table",
};

export interface ClousSQLQueryRequest extends CloudSQLQuery {}

export interface CloudSQLMetricsMetadataItem {
  type: string;
  help: string;
  unit?: string;
}
// https://github.com/grafana/grafana/blob/0c70308870e1748063b66274941772deba8cb76d/public/app/plugins/datasource/prometheus/types.ts
export interface CloudSQLMetricsMetadata {
  [metric: string]: CloudSQLMetricsMetadataItem[];
}

export const DataFormatTypeOptions = [
  { value: "JSON", label: "JSON" },
  { value: "CSV", label: "CSV" },
  { value: "PARQUET", label: "PARQUET" },
  { value: "AVRO", label: "AVRO" },
  { value: "ORC", label: "ORC" },
] as SelectableValue[];
/**
 * These are options configured for each DataSource instance
 */
export interface COSIBMDataSourceOptions extends DataSourceJsonData {
  //path?: string;
  apiKey: string; //Cloud API key
  instance_crn: string; // SQLQuery instance CRN
  source_cos_url?: string; // IBM COS with bucket where the data is stored
  table?: string; //HIVE table
  using_table: boolean; //decide between 'table' vs. 'cos_in_url'
  format_type?: string; // one of JSON, CSV, PARQUET
  target_cos_url: string; // IBM COS with bucket where the queried data is stored
  instance_rate_limit: number;
  sql_ui_link?: string;

  disableMetricsLookup?: boolean;
}

/**
 * Value that is used in the backend, but never sent over HTTP to the frontend
 */
export interface COSIBMSecureJsonData {}

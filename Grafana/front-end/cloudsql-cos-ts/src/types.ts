import { DataQuery, DataSourceJsonData, SelectableValue } from '@grafana/data';

export const FORMAT_OPTIONS: Array<SelectableValue<string>> = [
  { label: 'Time series', value: 'time_series' },
  { label: 'Table', value: 'table' },
];

export interface CloudSQLQuery extends DataQuery {
  queryText?: string; // sql_stmt?: string;

  id?: number; //track the ID of the associated datasource instance
  name?: string; //track the name of the associated datasource instance
  //not sure if these will be used
  //constant: number;
  format: string; //'timeseries' or something else?
  time_column?: string;
  metrics_column?: string; //the column from which uniques values represent different metrics
  get_result: boolean; // default is checked, i.e. the queried data is also returned
  //refId?: string; <--- from DataQuery
  ////PromQuery
  //expr: string;
  //format?: string;
  //instant?: boolean;
  //hinting?: boolean;
  //interval?: string;
  //intervalFactor?: number;
  //legendFormat?: string;
  //valueWithRefId?: boolean;
  //requestId?: string;
  //showingGraph?: boolean;
  //showingTable?: boolean;
  showingHelp: boolean;
}

export const defaultTSQuery: Partial<CloudSQLQuery> = {
  //return single time-series
  queryText: `WITH container_ts_table AS
  (SELECT field_name,
          ts
   FROM cos://s3.us-south.cloud-object-storage.appdomain.cloud/sql-query-cos-access-ts/jobid=d778a83b-23ae-4be4-bbb8-43168fd63f1c STORED AS PARQUET USING TIME_SERIES_FORMAT(KEY="field_name", timetick="time_stamp", value="observation") IN ts),
 tmp_table AS
(
SELECT field_name AS user_agent,
       ts_explode(ts_seg_sum(TS_SEGMENT_BY_TIME(ts, 604800000, 604800000))) AS (tt,
                                                                                value)
FROM container_ts_table)
 SELECT tt, log(value) as value
FROM tmp_table
WHERE user_agent LIKE "COS GO"
INTO cos://us-south/sql-query-cos-access-ts STORED AS PARQUET`,
  format: 'time_series',
  time_column: 'tt',
};
export const defaultMTSQuery: Partial<CloudSQLQuery> = {
  //return multiple time-series
  queryText: `WITH container_ts_table AS
  (SELECT field_name,
          ts
   FROM cos://s3.us-south.cloud-object-storage.appdomain.cloud/sql-query-cos-access-ts/jobid=d778a83b-23ae-4be4-bbb8-43168fd63f1c STORED AS PARQUET USING TIME_SERIES_FORMAT(KEY="field_name", timetick="time_stamp", value="observation") IN ts),
 tmp_table AS
(
SELECT
       ts_explode(ts_seg_sum(TS_SEGMENT_BY_TIME(ts, 604800000, 604800000))) AS (tt,
                                                                                value), field_name AS user_agent
FROM container_ts_table)
 SELECT tt, log(value) as value, user_agent
FROM tmp_table
INTO cos://us-south/sql-query-cos-access-ts STORED AS PARQUET`,
  format: 'time_series',
  time_column: 'tt',
  metrics_column: 'user_agent',
};
export const defaultQuery: Partial<CloudSQLQuery> = {
  //TODO
  //queryText: `SELECT
  //   UNIX_TIMESTAMP(<time_column>) as time_sec,
  //   <text_column> as text,
  //   <tags_column> as tags
  // FROM <table name>
  // WHERE $__timeFilter(time_column)
  // ORDER BY <time_column> ASC
  // LIMIT 100
  //`,
  queryText: `WITH container_ts_table AS
  (SELECT field_name,
          ts
   FROM cos://s3.us-south.cloud-object-storage.appdomain.cloud/sql-query-cos-access-ts/jobid=d778a83b-23ae-4be4-bbb8-43168fd63f1c STORED AS PARQUET USING TIME_SERIES_FORMAT(KEY="field_name", timetick="time_stamp", value="observation") IN ts)
SELECT field_name AS user_agent,
       ts_explode(ts_seg_sum(TS_SEGMENT_BY_TIME(ts, 604800000, 604800000))) AS (tt,
                                                                                value)
FROM container_ts_table INTO cos://us-south/sql-query-cos-access-ts STORED AS PARQUET`,
  //the below use macro names, e.g. {cos_in}, {cos_out}
  //queryText: `WITH container_ts_table AS
  //(SELECT field_name,
  //        ts
  // FROM {cos_in} STORED AS PARQUET USING TIME_SERIES_FORMAT(KEY="field_name", timetick="time_stamp", value="observation") IN ts)
  //SELECT field_name AS user_agent,
  //     ts_explode(ts_seg_sum(TS_SEGMENT_BY_TIME(ts, 604800000, 604800000))) AS (tt,
  //                                                                              value)
  //FROM container_ts_table INTO {cos_out} STORED AS PARQUET`
  //constant: 6.5,
  format: 'table',
};

export interface ClousSQLQueryRequest extends CloudSQLQuery {
  ////PromQueryRequest
  //step?: number;
  //requestId?: string;
  //start: number;
  //end: number;
  //headers?: any;
}
//NOTE: CloudWatch divides requests into different categories
// MetricRequest [from:string, to:string, queries: MetricQueryp[; debug?: boolean]]
// GetLogEventsRequest
// GetLogGroupFieldsRequest
// DescribeLogGroupsRequest
// StartQueryRequest [need logGroupNames | logGroupName]
//

export interface CloudSQLMetricsMetadataItem {
  ////PromMetricsMetadataItem
  type: string;
  help: string;
  unit?: string;
}
// https://github.com/grafana/grafana/blob/0c70308870e1748063b66274941772deba8cb76d/public/app/plugins/datasource/prometheus/types.ts
export interface CloudSQLMetricsMetadata {
  [metric: string]: CloudSQLMetricsMetadataItem[];
}

export const DataFormatTypeOptions = [
  { value: 'JSON', label: 'JSON' },
  { value: 'CSV', label: 'CSV' },
  { value: 'PARQUET', label: 'PARQUET' },
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

  ////PromOptions
  //timeInterval: string;
  //queryTimeout: string;
  //httpMethod: string;
  //directUrl: string;
  //customQueryParameters?: string;
  disableMetricsLookup?: boolean;
}

/**
 * Value that is used in the backend, but never sent over HTTP to the frontend
 */
export interface COSIBMSecureJsonData {}

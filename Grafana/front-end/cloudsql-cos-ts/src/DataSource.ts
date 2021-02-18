import defaults from 'lodash/defaults';
//import { from, of, Observable, forkJoin } from 'rxjs';
//import { Observable } from 'rxjs';
import { getBackendSrv, BackendSrvRequest, getTemplateSrv } from '@grafana/runtime';
import { ScopedVars } from '@grafana/data';
import { TimeSeries } from '@grafana/data';
import { DataFrame } from '@grafana/data';
import { toDataFrame } from '@grafana/data';

import {
  DataQueryRequest,
  DataQueryResponse,
  DataSourceApi,
  DataSourceInstanceSettings,
  MutableDataFrame,
  FieldType,
  //DefaultTimeRange,
} from '@grafana/data';

import { CloudSQLQuery, COSIBMDataSourceOptions, defaultQuery } from './types';
import CloudSQLLanguageProvider from './sql/language_provider';

//export const CLOUDSQL_ENDPOINT = '/cloudsql/api/v1';

function extend(obj: any, src: any) {
  Object.keys(src).forEach(function(key) {
    obj[key] = src[key];
  });
  return obj;
}
export class COSIBMDataSource extends DataSourceApi<CloudSQLQuery, COSIBMDataSourceOptions> {
  //server_url: any;
  jsonData: COSIBMDataSourceOptions;
  instanceSettings: DataSourceInstanceSettings<COSIBMDataSourceOptions>;
  url: string;

  ////Cloudwatch
  //type: any;
  //proxyUrl: any;
  //defaultRegion: any;
  //datasourceName: string; // Hive metastore
  //debouncedAlert: (datasourceName: string, region: string) => void;
  //debouncedCustomAlert: (title: string, message: string) => void;
  //logQueries: Record<string, { id: string; region: string }>;
  languageProvider: CloudSQLLanguageProvider;

  ////Prometheus
  // type: string;
  // editorSrc: string;
  // ruleMappings: { [index: string]: string };
  // url: string;
  // directUrl: string;
  // basicAuth: any;
  // withCredentials: any;
  // metricsNameCache: any;
  // interval: string;
  // queryTimeout: string;
  // httpMethod: string;
  // languageProvider: PrometheusLanguageProvider;
  lookupsDisabled: boolean;
  // resultTransformer: ResultTransformer;
  // customQueryParameters: any;

  constructor(
    instanceSettings: DataSourceInstanceSettings<COSIBMDataSourceOptions>
    //private templateSrv: TemplateSrv,
    //private timeSrv: TimeSrv
  ) {
    // NOTE: we can get to the webpages (e.g. ConfigEditor, QueryEditor) via this.components
    // which is of type DataSourcePluginComponents

    super(instanceSettings);
    //this.name = instanceSettings.name;
    //this.id = instanceSettings.id;
    ////this.interval = instanceSettings.jsonData.;

    this.instanceSettings = instanceSettings;
    this.jsonData = instanceSettings.jsonData;
    this.url = instanceSettings.url!;
    //this.server_url = instanceSettings.url;
    //console.log(instanceSettings.jsonData.apiKey);
    // this.type = 'cloudwatch';
    // this.proxyUrl = instanceSettings.url;
    // this.defaultRegion = instanceSettings.jsonData.defaultRegion;
    // this.datasourceName = instanceSettings.name;
    // this.standardStatistics = ['Average', 'Maximum', 'Minimum', 'Sum', 'SampleCount'];
    // this.debouncedAlert = memoizedDebounce(displayAlert, AppNotificationTimeout.Error);
    // this.debouncedCustomAlert = memoizedDebounce(displayCustomError, AppNotificationTimeout.Error);
    // this.logQueries = {};

    //this.type = 'prometheus';
    //this.editorSrc = 'app/features/prometheus/partials/query.editor.html';
    //this.url = instanceSettings.url;
    //this.basicAuth = instanceSettings.basicAuth;
    //this.withCredentials = instanceSettings.withCredentials;
    //this.interval = instanceSettings.jsonData.timeInterval || '15s';
    //this.queryTimeout = instanceSettings.jsonData.queryTimeout;
    //this.httpMethod = instanceSettings.jsonData.httpMethod || 'GET';
    //this.directUrl = instanceSettings.jsonData.directUrl;
    //this.resultTransformer = new ResultTransformer(templateSrv);
    //this.ruleMappings = {};
    this.languageProvider = new CloudSQLLanguageProvider(this);
    this.lookupsDisabled = instanceSettings.jsonData.disableMetricsLookup!;
    //this.customQueryParameters = new URLSearchParams(instanceSettings.jsonData.customQueryParameters);
  }

  //async cloudsqlRequest_remote_python(url: string, data: CloudSQLQuery){
  //  let myUrl = url + "/login";
  //  //content = { jsonData};
  //  let content = JSON.stringify({});
  //  const response = await fetch(myUrl, {
  //    method: 'POST',
  //    body: content,
  //    headers: {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'} });

  //  if (!response.ok) { /* Handle */ }

  //  // If you care about a response:
  //  if (response.body !== null) {
  //    // body is ReadableStream<Uint8Array>
  //    // parse as needed, e.g. reading directly, or
  //    const asString = new TextDecoder("utf-8").decode(response.body);
  //    // and further:
  //    const asJSON = JSON.parse(asString);  // implicitly 'any', make sure to verify type on runtime.
  //  }
  //}
  //async pythonRequest_builtin_backend(url: string, data: MetricRequest) {
  //  const options = {
  //    method: 'POST',
  //    url,
  //    data
  //  }
  //  const result = await getBackendSrv().datasourceRequest(options);
  //  return result.data;
  //}

  //doMetricQueryRequests(subtype: string, parameters:any ) {
  //  const TSDB_QUERY_ENDPOINT = '/api/tsdb/query';
  //  //const range = this.timeSrv.timeRange();
  //  const range = DefaultTimeRange;
  //  let metrics = {
  //     from: range.from.valueOf().toString(),
  //     to: range.to.valueOf().toString(),
  //     queries: [
  //       {
  //         refId: 'metricFindQuery',
  //         intervalMs: 1, // dummy
  //         maxDataPoints: 1, // dummy
  //         datasourceId: this.id,
  //         type: 'metricFindQuery',
  //         subtype: subtype,
  //         ...parameters,
  //       },
  //     ],
  //   };
  //  //return this.pythonRequest(TSDB_QUERY_ENDPOINT, metrics).then((r: TSDBResponse) => {
  //  //  return this.transformSuggestDataFromtable(r);
  //  //})
  //}

  async _query_default(options: DataQueryRequest<CloudSQLQuery>): Promise<DataQueryResponse> {
    //NOTE : this one does not connect to remote server at all
    const { range } = options;
    const from = range!.from.valueOf();
    const to = range!.to.valueOf();

    // Return a constant for each query.
    const data = options.targets.map(target => {
      const query = defaults(target, defaultQuery);
      return new MutableDataFrame({
        refId: query.refId,
        fields: [
          { name: 'Time', values: [from, to], type: FieldType.time },
          //{ name: 'Value', values: [query.constant, query.constant], type: FieldType.number },
          { name: 'Value', values: [5, 5], type: FieldType.number },
        ],
      });
    });
    return { data };
  }
  interpolateVariablesInQueries(queries: CloudSQLQuery[], scopedVars: ScopedVars): CloudSQLQuery[] {
    if (!queries.length) {
      return queries;
    }
    return queries.map(query => {
      const expandedQuery = {
        ...query,
        //queryText: getTemplateSrv().replace(query.queryText, scopedVars),
        queryText: getTemplateSrv().replace(query.queryText, undefined),
      };
      return expandedQuery;
    });
  }
  buildQueryParameters(options: DataQueryRequest<CloudSQLQuery>) {
    ////remove placeholder targets
    //options.targets = _.filter(options.targets, target => {
    //  return target.target !== 'select metric';
    //});

    //var targets = _.map(options.targets, target => {
    //  return {
    //    target: this.templateSrv.replace(target.target, options.scopedVars, 'regex'),
    //    refId: target.refId,
    //    hide: target.hide,
    //    type: target.type || 'timeserie',
    //  };
    //});
    let new_options = options;
    new_options.targets = this.interpolateVariablesInQueries(options.targets, options.scopedVars);

    //options.targets = targets;
    return new_options;
  }
  //NOTE: In old code, the constructor accept 4 arguments
  //constructor(instanceSettings, $q, backendSrv, templateSrv)
  // ... that's how we store 'backendSrv
  // Now, we can import
  // import { BackendSrv as BackendService, BackendSrvRequest } from '@grafana/runtime';
  doRequest(options: BackendSrvRequest): Promise<DataQueryResponse> {
    //NOTE:
    // retry?: number;
    //headers?: any;
    //method?: string; //GET, PUT, POST
    //showSuccessAlert?: boolean; //display an alert when successful
    // requestId?: string;// IMPORTANT: having this is useful, as the backend can manage, and cancel existing query, and launch a new one if the two have the same 'refId'
    //[key: string]: any;
    //options.withCredentials = this.withCredentials;
    //options.headers = this.headers;

    return getBackendSrv().datasourceRequest(options);
    ////since Grafana 6.6, we can do this
    //getBackendSrv().get(‘http://your.url/api').then(result => {
    //this.result = result;
    //this.$scope.$digest();
    //});
  }
  processResult(response: any, query: DataQueryRequest<CloudSQLQuery>): any {
    //// Keeping original start/end for transformers
    const transformerOptions = {};
    //const transformerOptions = {
    //  format: target.format,
    //  step: query.step,
    //  legendFormat: target.legendFormat,
    //  start: query.start,
    //  end: query.end,
    //  query: query.expr,
    //  responseListLength,
    //  refId: target.refId,
    //  valueWithRefId: target.valueWithRefId,
    //  meta: {
    //    /** Fix for showing of Prometheus results in Explore want to show result of instant query in table and the rest of time series in graph */
    //    preferredVisualisationType: query.instant ? 'table' : 'graph',
    //  },
    //};
    const series = this.transform(response, transformerOptions);
    return series;
  }

  transform(response: any, options: any): Array<DataFrame | TimeSeries> {
    //const seriesList = [];
    //seriesList.push();
    const seriesList = response.data.data.result;
    return seriesList;
  }

  async _query_return_dataframes(options: DataQueryRequest<CloudSQLQuery>): Promise<DataQueryResponse> {
    // NOTE: This one actually connect to the server

    // 1. first extract what is needed to send to the server
    var query = this.buildQueryParameters(options);
    var result = this.doRequest({
      url: this.url + '/query',
      data: query,
      method: 'POST',
    });
    return result.then(response => {
      return {
        data: response.data.map(result => {
          //The toDataFrame() function converts a legacy response, such as TimeSeries or Table, to a DataFrame
          return toDataFrame(result);
        }),
      };
    });
    //https://grafana.com/docs/grafana/latest/developers/plugins/migration-guide/#migrate-to-data-frames
  }
  async _query_default_2(options: DataQueryRequest<CloudSQLQuery>): Promise<DataQueryResponse> {
    // NOTE: This one actually connect to the server

    // 1. first extract what is needed to send to the server
    var query = this.buildQueryParameters(options);
    //query.targets = query.targets.filter(t => !t.hide);
    //if (query.targets.length <= 0) {
    //  return this.q.when({ data: [] });
    //}

    //if (this.templateSrv.getAdhocFilters) {
    //  query.adhocFilters = this.templateSrv.getAdhocFilters(this.name);
    //} else {
    //  query.adhocFilters = [];
    //}

    var result = this.doRequest({
      url: this.url + '/query',
      data: query,
      method: 'POST',
    });
    return result.then(response => {
      return response;
    });

    //return getBackendSrv().post(this.url+'/query', query).then(response=> {
    //  const data = this.processResult(response, options);
    //  //this.result = result;
    //  //this.$scope.$digest();
    //  //return response;
    //  return {
    //    data,
    //    key: options.requestId,
    //    //state:
    //  } as DataQueryResponse;
    //});
  }
  ///query(options: DataQueryRequest<CloudSQLQuery>):  Observable<DataQueryResponse>
  async query(options: DataQueryRequest<CloudSQLQuery>): Promise<DataQueryResponse> {
    // REQUIREMENT
    //  //must returns an instance of DataQueryResponse
    //  //which must contains at least the field
    //  // data: DataQueryResponseData[];
    //  //with
    //  // DataQueryResponseData = DataFrame | DataFrameDTO | LegacyResponseData;
    //  // NOTE:  DataFrame can represent both TimeSeries and TableData (since Grafana v6.2)
    //  // type LegacyResponseData = TimeSeries | TableData | any;
    //  return {data};

    //const startMs = Date.now() - 10 * 60 * 1000; // last 10 minutes
    //const start = `${startMs}000000`; //API expects unit in nanoseconds
    ////this._request(`${this.server_url}`)
    //const { range } = options;
    //const from = range!.from.valueOf();
    //const to = range!.to.valueOf();

    //// Return a constant for each query.
    //const data = options.targets.map(target => {
    //  const query = defaults(target, defaultQuery);
    //  return new MutableDataFrame({
    //    refId: query.refId,
    //    fields: [
    //      { name: 'Time', values: [from, to], type: FieldType.time },
    //      { name: 'Value', values: [query.constant, query.constant], type: FieldType.number },
    //    ],
    //  });
    //});

    //  //data = {};
    //return { data };

    //DEFAULT behavior
    //return this._query_default(options);
    //return this._query_default_2(options);
    //NEW behavior
    return this._query_return_dataframes(options);

    //What an expected data look like for Grafana?
    // Zipkin example: a dictionary with 'data' as key
    // . .... and value is an array
    //const emptyDataQueryResponse = {
    //  data: [
    //    new MutableDataFrame({
    //      fields: [
    //        {
    //          name: 'trace',
    //          type: FieldType.trace,
    //          values: [],
    //        },
    //      ],
    //    }),
    //  ],
    //function responseToDataQueryResponse(response: { data: ZipkinSpan[] }): DataQueryResponse {
    //  return {
    //    data: [
    //      new MutableDataFrame({
    //        fields: [
    //          {
    //            name: 'trace',
    //            type: FieldType.trace,
    //            // There is probably better mapping than just putting everything in as a single value but that's how
    //            // we do it with jaeger and is the simplest right now.
    //            values: response?.data ? [transformResponse(response?.data)] : [],
    //          },
    //        ],
    //      }),
    //    ],
    //  };
    //}
  }

  async testDatasource() {
    //console.log(this.jsonData);
    //console.log(this.jsonData.apiKey);
    // Implement a health check for your data source.
    //let status, message;
    //const defaultErrorMessage = 'Cannot connect to CloudSQL instance';

    let myUrl = this.url + '/login';

    let tmp = this.jsonData;
    let id = this.instanceSettings.id;
    let name = this.instanceSettings.name;
    let id_name: { [id: string]: string | number } = {};
    id_name['id'] = id;
    id_name['name'] = name;

    //TODO: add the check 'using_table' so that
    // we can also configure HIVE metastore

    tmp = extend(tmp, id_name);
    let content = JSON.stringify(this.jsonData);
    //let content = JSON.stringify({});
    //NOTE: body type must match Content-Type header
    const response = await fetch(myUrl, {
      method: 'POST',
      body: content,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        //'Content-Type': 'application/x-www-form-urlencoded',
        //'Content-Type': 'application/json',
      },
    });
    //let response = this.doRequest({
    //  url: myUrl,
    //  data: content,
    //  method: 'POST',
    //}).then(response => {
    //  return response;
    //});

    //above fetch returns a Stream object
    //response.json()  // <---- then here iis the Promise<any> object
    //let result = response.json();
    // {
    //   'status': 'success',
    //   'employees' : [
    //      { 'id': 12, 'name': 'Tom', 'department': 'finance' },
    //      { 'id': 34, 'name': 'Dick', 'department': 'admin' },
    //      { 'id': 56, 'name': 'Harry', 'department': 'marketing' }
    //   ]
    //}
    //var employees = {};
    //for (var i = 0, emp; i < result.employees.length; i++) {
    //  emp = result.employees[i];
    //  employees[ emp.id ] = emp;
    //}
    //console.log(employees[56].name);       // logs "Harry"
    //console.log(employees[56].department); // logs "marketing"
    //return {
    //  status: 'failed',
    //  message: response.text(),
    //  title: 'TUAN',
    //};
    //open("~/grafana.log", 'wa').write(response.statusText)

    if (response.status < 300) {
      //always CONNECT successfully
      // you can use one of this
      return {
        status: 'success',
        message: response.statusText, //'Success',
        //message: JSON.stringify(response.json()),
        //title: 'Connected to CloudSQL',
      };
    } else if (response.status < 500) {
      let text = await response.text();
      //window.alert(JSON.stringify(text));
      //window.alert(response.status); //JSON.stringify(text));
      return {
        status: 'error',
        //message: JSON.stringify(text),
        message: text,
      };
    } else {
      return {
        status: 'error',
        message: response.statusText,
      };
    }

    //always CONNECT successfully
    // you can use one of this
    return {
      status: 'success',
      message: 'Success',
    };
    //return Promise.resolve({});
    //return Promise.resolve({
    //  status: 200,
    //});
    //return Promise.resolve({
    //  status: 200,
    //  data: {
    //    values: ['avalue'],
    //  },
    //});

    //Prometheus
    // const now = new Date().getTime();
    // const query = { expr: '1+1' } as PromQueryRequest;
    // const response = await this.performInstantQuery(query, now / 1000);
    // return response.data.status === 'success'
    //   ? { status: 'success', message: 'Data source is working' }
    //   : { status: 'error', message: response.error };

    //CloudWatch
    //  // use billing metrics for test
    //  const region = this.defaultRegion;
    //  const namespace = 'AWS/Billing';
    //  const metricName = 'EstimatedCharges';
    //  const dimensions = {};

    //  return this.getDimensionValues(region, namespace, metricName, 'ServiceName', dimensions).then(() => ({
    //    status: 'success',
    //    message: 'Data source is working',
    //  }));
  }

  testDatasource_old() {
    //another way to issue Rest API is using the functionality provided by Grafana
    return getBackendSrv()
      .datasourceRequest({
        url: '/api/tsdb/query',
        method: 'POST',
        data: {
          from: '5m',
          to: 'now',
          queries: [
            {
              refId: 'A',
              intervalMs: 1,
              maxDataPoints: 1,
              datasourceId: this.id,
              rawSql: 'SELECT 1',
              format: 'table',
            },
          ],
        },
      })
      .then((res: any) => {
        return { status: 'success', message: 'Database Connection OK' };
      })
      .catch((err: any) => {
        console.log(err);
        if (err.data && err.data.message) {
          return { status: 'error', message: err.data.message };
        } else {
          return { status: 'error', message: err.status };
        }
      });
  }
}
//export default COSIBMDataSource;

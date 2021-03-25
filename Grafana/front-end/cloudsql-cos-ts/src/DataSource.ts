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
import defaults from "lodash/defaults";
import {
  getBackendSrv,
  BackendSrvRequest,
  getTemplateSrv,
} from "@grafana/runtime";

import {
  ScopedVars,
  TimeSeries,
  DataFrame,
  toDataFrame,
  DataQueryRequest,
  DataQueryResponse,
  DataSourceApi,
  DataSourceInstanceSettings,
  MutableDataFrame,
  FieldType,
  //DefaultTimeRange,
} from "@grafana/data";

import { CloudSQLQuery, COSIBMDataSourceOptions, defaultQuery } from "./types";
import CloudSQLLanguageProvider from "./sql/language_provider";

//export const CLOUDSQL_ENDPOINT = '/cloudsql/api/v1';

function extend(obj: any, src: any) {
  Object.keys(src).forEach(function (key) {
    obj[key] = src[key];
  });
  return obj;
}
export class COSIBMDataSource extends DataSourceApi<
  CloudSQLQuery,
  COSIBMDataSourceOptions
> {
  //server_url: any;
  jsonData: COSIBMDataSourceOptions;
  instanceSettings: DataSourceInstanceSettings<COSIBMDataSourceOptions>;
  url: string;

  languageProvider: CloudSQLLanguageProvider;

  lookupsDisabled: boolean;

  constructor(
    instanceSettings: DataSourceInstanceSettings<COSIBMDataSourceOptions>
  ) {
    // NOTE: we can get to the webpages (e.g. ConfigEditor, QueryEditor) via this.components
    // which is of type DataSourcePluginComponents

    super(instanceSettings);

    this.instanceSettings = instanceSettings;
    this.jsonData = instanceSettings.jsonData;
    this.url = instanceSettings.url!;

    this.languageProvider = new CloudSQLLanguageProvider(this);
    this.lookupsDisabled = instanceSettings.jsonData.disableMetricsLookup!;
  }

  async _query_default(
    options: DataQueryRequest<CloudSQLQuery>
  ): Promise<DataQueryResponse> {
    //NOTE : this one does not connect to remote server at all
    const { range } = options;
    const from = range!.from.valueOf();
    const to = range!.to.valueOf();

    // Return a constant for each query.
    const data = options.targets.map((target) => {
      const query = defaults(target, defaultQuery);
      return new MutableDataFrame({
        refId: query.refId,
        fields: [
          { name: "Time", values: [from, to], type: FieldType.time },
          //{ name: 'Value', values: [query.constant, query.constant], type: FieldType.number },
          { name: "Value", values: [5, 5], type: FieldType.number },
        ],
      });
    });
    return { data };
  }
  interpolateVariablesInQueries(
    queries: CloudSQLQuery[],
    scopedVars: ScopedVars
  ): CloudSQLQuery[] {
    if (!queries.length) {
      return queries;
    }
    return queries.map((query) => {
      const expandedQuery = {
        ...query,
        //queryText: getTemplateSrv().replace(query.queryText, scopedVars),
        queryText: getTemplateSrv().replace(query.queryText, undefined),
      };
      return expandedQuery;
    });
  }
  buildQueryParameters(options: DataQueryRequest<CloudSQLQuery>) {
    let new_options = options;
    new_options.targets = this.interpolateVariablesInQueries(
      options.targets,
      options.scopedVars
    );

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
    const series = this.transform(response, transformerOptions);
    return series;
  }

  transform(response: any, options: any): Array<DataFrame | TimeSeries> {
    //const seriesList = [];
    //seriesList.push();
    const seriesList = response.data.data.result;
    return seriesList;
  }

  async _query_return_dataframes(
    options: DataQueryRequest<CloudSQLQuery>
  ): Promise<DataQueryResponse> {
    // NOTE: This one actually connect to the server

    // 1. first extract what is needed to send to the server
    var query = this.buildQueryParameters(options);
    var result = this.doRequest({
      url: this.url + "/query",
      data: query,
      method: "POST",
    });
    return result.then((response) => {
      return {
        data: response.data.map((result) => {
          //The toDataFrame() function converts a legacy response, such as TimeSeries or Table, to a DataFrame
          return toDataFrame(result);
        }),
      };
    });
    //https://grafana.com/docs/grafana/latest/developers/plugins/migration-guide/#migrate-to-data-frames
  }
  async _query_default_2(
    options: DataQueryRequest<CloudSQLQuery>
  ): Promise<DataQueryResponse> {
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
      url: this.url + "/query",
      data: query,
      method: "POST",
    });
    return result.then((response) => {
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
  async query(
    options: DataQueryRequest<CloudSQLQuery>
  ): Promise<DataQueryResponse> {
    // REQUIREMENT
    //  //must returns an instance of DataQueryResponse
    //  //which must contains at least the field
    //  // data: DataQueryResponseData[];
    //  //with
    //  // DataQueryResponseData = DataFrame | DataFrameDTO | LegacyResponseData;
    //  // NOTE:  DataFrame can represent both TimeSeries and TableData (since Grafana v6.2)
    //  // type LegacyResponseData = TimeSeries | TableData | any;
    //  return {data};

    return this._query_return_dataframes(options);
  }

  async testDatasource() {
    let myUrl = this.url + "/login";

    let tmp = this.jsonData;
    let id = this.instanceSettings.id;
    let name = this.instanceSettings.name;
    let id_name: { [id: string]: string | number } = {};
    id_name["id"] = id;
    id_name["name"] = name;

    //TODO: add the check 'using_table' so that
    // we can also configure HIVE metastore

    tmp = extend(tmp, id_name);
    let content = JSON.stringify(this.jsonData);
    //let content = JSON.stringify({});
    //NOTE: body type must match Content-Type header
    const response = await fetch(myUrl, {
      method: "POST",
      body: content,
      headers: {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        //'Content-Type': 'application/x-www-form-urlencoded',
        //'Content-Type': 'application/json',
      },
    });

    if (response.status < 300) {
      //always CONNECT successfully
      // you can use one of this
      return {
        status: "success",
        message: response.statusText, //'Success',
        //message: JSON.stringify(response.json()),
        //title: 'Connected to CloudSQL',
      };
    } else if (response.status < 500) {
      let text = await response.text();
      //window.alert(JSON.stringify(text));
      //window.alert(response.status); //JSON.stringify(text));
      return {
        status: "error",
        //message: JSON.stringify(text),
        message: text,
      };
    } else {
      return {
        status: "error",
        message: response.statusText,
      };
    }

    //always CONNECT successfully
    // you can use one of this
    return {
      status: "success",
      message: "Success",
    };
  }

  testDatasource_old() {
    //another way to issue Rest API is using the functionality provided by Grafana
    return getBackendSrv()
      .datasourceRequest({
        url: "/api/tsdb/query",
        method: "POST",
        data: {
          from: "5m",
          to: "now",
          queries: [
            {
              refId: "A",
              intervalMs: 1,
              maxDataPoints: 1,
              datasourceId: this.id,
              rawSql: "SELECT 1",
              format: "table",
            },
          ],
        },
      })
      .then((res: any) => {
        return { status: "success", message: "Database Connection OK" };
      })
      .catch((err: any) => {
        console.log(err);
        if (err.data && err.data.message) {
          return { status: "error", message: err.data.message };
        } else {
          return { status: "error", message: err.status };
        }
      });
  }
}
//export default COSIBMDataSource;

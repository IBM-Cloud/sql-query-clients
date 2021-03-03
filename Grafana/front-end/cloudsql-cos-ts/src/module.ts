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
import { DataSourcePlugin } from '@grafana/data';
import { COSIBMDataSource } from './DataSource';
import { ConfigEditor } from './ConfigEditor';
import { QueryEditor } from './QueryEditor';
import CloudSQLCheatSheet from './CheatSheet';
import CloudSQLExploreQueryEditor from './ExploreQueryEditor';
import { CloudSQLQuery, COSIBMDataSourceOptions } from './types';

export const plugin = new DataSourcePlugin<COSIBMDataSource, CloudSQLQuery, COSIBMDataSourceOptions>(COSIBMDataSource)
  .setConfigEditor(ConfigEditor)
  //.setExploreMetricsQueryField(CloudSQLExploreQueryEditor)
  .setExploreQueryField(CloudSQLExploreQueryEditor)
  //.setExploreMetricsQueryField(CloudSQLExploreQueryEditor)
  //.setExploreLogsQueryField(CloudSQLExploreQueryEditor)
  .setExploreStartPage(CloudSQLCheatSheet)
  .setQueryEditor(QueryEditor);

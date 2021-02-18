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

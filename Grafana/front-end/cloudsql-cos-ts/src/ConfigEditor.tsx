import React, { PureComponent } from 'react';
import { DataSourceHttpSettings } from '@grafana/ui';
import { DataSourcePluginOptionsEditorProps } from '@grafana/data';
import { CloudSQLSettings } from './configuration/CloudSQLSettings';
import { COSIBMDataSourceOptions } from './types';
//import { COSIBMDataSourceOptions, COSIBMSecureJsonData } from './types';

export type Props = DataSourcePluginOptionsEditorProps<COSIBMDataSourceOptions>;
//export type Props = DataSourcePluginOptionsEditorProps<COSIBMDataSourceOptions, COSIBMSecureJsonData>;

export class ConfigEditor extends PureComponent<Props> {
  render() {
    // a props is split into 2 parts: the data part, and the callback part
    const { options, onOptionsChange } = this.props;

    return (
      <>
        <DataSourceHttpSettings
          defaultUrl="http://localhost:18081"
          dataSourceConfig={options}
          showAccessOptions={true}
          //@ts-ignore
          onChange={onOptionsChange}
        />
        <CloudSQLSettings
          value={options.jsonData}
          onChange={newValue => onOptionsChange({ ...options, jsonData: newValue })}
        />
      </>
    );
  }
}
export default ConfigEditor;

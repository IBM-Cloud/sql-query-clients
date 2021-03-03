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

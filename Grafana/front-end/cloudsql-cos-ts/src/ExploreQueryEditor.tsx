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
import React, { memo, ChangeEvent, useState } from 'react';

// Types
import { ExploreQueryFieldProps, SelectableValue } from '@grafana/data';

import { COSIBMDataSource } from './DataSource';
//import { FORMAT_OPTIONS, CloudSQLQuery, COSIBMDataSourceOptions, defaultMTSQuery } from './types';
import { FORMAT_OPTIONS, CloudSQLQuery, COSIBMDataSourceOptions } from './types';

import { CloudSQLQueryField } from './configuration/QueryFields';
//import { QueryField } from '@grafana/ui';
//import { defaults } from 'lodash';
//import CloudSQLQueryField from './CloudSQLQueryField';
//import { CloudSQLExploreExtraField } from './CloudSQLExploreExtraField';
import { LegacyForms } from '@grafana/ui';
const { Select, FormField, Switch } = LegacyForms;

import { CloudSQLHelp } from './sql/help';

export type Props = ExploreQueryFieldProps<COSIBMDataSource, CloudSQLQuery, COSIBMDataSourceOptions>;
// NOTE: It has those provided by QueryFieldProps
// {from here
//NOTE: .datasource: COSIBMDataSource
// .          .query: CloudSQLQuery
// .           (some others .data: PanelData, .exploreMode: ExploreMode, .exploreId?: any, history?: HistoryItem[])
// to here}
// and new stuffs
// .  ..absoluteRange?: AbsoluteTimeRange;

//export interface LokiQueryFieldFormProps extends ExploreQueryFieldProps<LokiDatasource, LokiQuery, LokiOptions> {
//  history: LokiHistoryItem[];
//  syntax: Grammar;
//  logLabelOptions: CascaderOption[];
//  syntaxLoaded: boolean;
//  absoluteRange: AbsoluteTimeRange;
//  onLoadOptions: (selectedOptions: CascaderOption[]) => void;
//  onLabelsRefresh?: () => void;
//  ExtraFieldElement?: ReactNode;
//}
//type LokiQueryFieldProps = Omit<
//  LokiQueryFieldFormProps,
//  'syntax' | 'syntaxLoaded' | 'onLoadOptions' | 'onLabelsRefresh' | 'logLabelOptions'
//>;

export function CloudSQLExploreQueryEditor(props: Props) {
  const [showingHelp, setShowingHelp] = useState(false);
  //const { query, data, datasource, history, onChange, onRunQuery } = props;
  //const { query, onChange } = props;
  //const query = defaults(props.query, defaultMTSQuery);
  const query = props.query;
  const ds = props.datasource;
  query.name = ds.name;
  query.id = ds.id;
  //const {queryText, constant}  = query;
  //props.query.showingHelp = false;
  //const onShowingHelpChange = (value: boolean) => {
  //  setShowingHelp(value);
  //  //onChange({
  //  //  ...query,
  //  //  showingHelp: value,
  //  //});
  //};
  //const onShowingHelpChange = useCallback(
  //  (value: any) => {
  //    setShowingHelp(value);
  //    onChange({
  //      ...query,
  //      showingHelp: value,
  //    });
  //  },
  //  [query, onChange]
  //);

  //function onChangeQueryStep(value: string) {
  //  const { query, onChange } = props;
  //  const nextQuery = { ...query, interval: value };
  //  onChange(nextQuery);
  //}
  //const onQueryChange = (value: string, override?: boolean) => {
  //  //const { query, onChange, onRunQuery } = props;
  //  const { query, onChange } = props;

  //  if (onChange) {
  //    // Update the query whenever the query field changes.
  //    onChange({ ...query, queryText: value });

  //    // Run the query on Enter.
  //    //if (override && onRunQuery) {
  //    //onRunQuery();
  //    //}
  //  }
  //};
  const onTimeColumnChange = (event: ChangeEvent<HTMLInputElement>) => {
    //const { onChange, query, onRunQuery } = props;
    const { onChange, query } = props;
    onChange({ ...query, time_column: event.target.value });
    //onRunQuery(); // executes the query
  };
  const onMetricsColumnChange = (event: ChangeEvent<HTMLInputElement>) => {
    //const { onChange, query, onRunQuery } = props;
    const { onChange, query } = props;
    onChange({ ...query, metrics_column: event.target.value });
    //onRunQuery(); // executes the query
  };
  const onFormatChange = (option: SelectableValue<string>) => {
    //const { query, onChange, onRunQuery } = props;
    const { query } = props;
    //const { query, onChange } = props;
    query.format = option.value!;
    //this.setState({ formatOption: option }, this.onRunQuery);
    //if (onChange) {
    //  const nextQuery = {
    //    ...query,
    //    format: option.value!,
    //  };
    //  onChange(nextQuery);
    //  //  // Update the query whenever the query field changes.
    //  //  onChange({ ...query, queryText: value });
    //  //
    //  //onRunQuery();
    //}
  };

  //function onStepChange(e: React.SyntheticEvent<HTMLInputElement>) {
  //  if (e.currentTarget.value !== query.interval) {
  //    onChangeQueryStep(e.currentTarget.value);
  //  }
  //}

  //function onReturnKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
  //  if (e.key === 'Enter') {
  //    onRunQuery();
  //  }
  //}

  //return (
  //  <CloudSQLQueryField
  //    datasource={datasource}
  //    query={query}
  //    onRunQuery={onRunQuery}
  //    onChange={onChange}
  //    onBlur={() => {}}
  //    history={history}
  //    data={data}
  //    ExtraFieldElement={
  //      <CloudSQLExploreExtraField
  //        label={'Step'}
  //        onChangeFunc={onStepChange}
  //        onKeyDownFunc={onReturnKeyDown}
  //        value={query.interval || ''}
  //        hasTooltip={true}
  //        tooltipContent={
  //          'Time units can be used here, for example: 5s, 1m, 3h, 1d, 1y (Default if no unit is specified: s)'
  //        }
  //      />
  //    }
  //  />
  //);
  //return <h2>My Explore query editor</h2>;
  return (
    <>
      <h3>IBM CloudSQL explorer</h3>
      {/*       <FormField
        width={4}
        value={query.constant}
        //onChange={onConstantChange}
        label="Constant"
        type="number"
        step="0.1"
      ></FormField> */}
      {/*       <FormField width={10} value={query.format} label="Test" type="string"></FormField> */}
      <div className="display:flex gf-form">
        <FormField
          width={13}
          labelWidth={7}
          value={query.time_column}
          onChange={onTimeColumnChange}
          label="Time column"
          tooltip="If Format is 'Time series', then type in the column name that contains the datetime data. If empty, then by default it assumes the first column is 'time', and the second column is 'value'"
          type="string"
        ></FormField>
        <FormField
          width={13}
          labelWidth={9}
          value={query.metrics_column}
          onChange={onMetricsColumnChange}
          label="Metrics column"
          tooltip="If Format is 'Time series' and the SQL query returns 3-columns, then type in the column name that contains the metrics data. If empty, then by default it assumes the third column is 'metrics'"
          type="string"
        ></FormField>
      </div>
      <div className="gf-form">
        <div className="gf-form-label width-7">Format</div>
        <Select
          width={7}
          isSearchable={false}
          options={FORMAT_OPTIONS}
          onChange={onFormatChange}
          /*           value={FORMAT_OPTIONS.find(option => option.value === query.format) || FORMAT_OPTIONS[0]} */
          value={FORMAT_OPTIONS.find(option => option.value! === query.format)}
          //defaultValue =
        />
        <Switch
          label="Show Help"
          labelClass="width-7"
          //TODO  - replace checked with 'value
          //https://github.com/grafana/grafana/blob/71fffcb17c096452509191a58b3e1c5ec9f70395/packages/grafana-ui/src/components/Switch/Switch.tsx
          // and replace that with a variable
          checked={showingHelp}
          //onChange={onShowingHelpChange}
          //onChange={event => {
          //  props.query.showingHelp = !props.query.showingHelp;
          //}}
          onChange={event => {
            //props.query.showingHelp = !props.query.showingHelp;
            setShowingHelp(!showingHelp);
          }}
          //onChange={event => {
          //  onShowingHelpChange({ showingHelp: event!.currentTarget.checked });
          //}}
          tooltip="Tips on how to write the Cloud SQL query"
        />
      </div>
      <CloudSQLQueryField
        datasource={props.datasource}
        query={props.query}
        range={props.range}
        onRunQuery={props.onRunQuery}
        onChange={props.onChange}
        onBlur={() => {}}
        history={props.history}
        data={props.data}
        // TODO
        //ExtraFieldElement={
        //  <PromExploreExtraField
        //    queryType={query.range && query.instant ? 'both' : query.instant ? 'instant' : 'range'}
        //    stepValue={query.interval || ''}
        //    onQueryTypeChange={onQueryTypeChange}
        //    onStepChange={onStepChange}
        //    onKeyDownFunc={onReturnKeyDown}
        //  />
        //}
      />
      {/*
        //in query window
        <PromQueryField
          datasource={datasource}
          query={query}
          onRunQuery={this.onRunQuery}
          onChange={this.onFieldChange}
          history={[]}
          data={data}
        />
        //in explore window
      <PromQueryField
        datasource={datasource}
        query={query}
        onRunQuery={onRunQuery}
        onChange={onChange}
        onBlur={() => {}}
        history={history}
        data={data}
        ExtraFieldElement={
          <PromExploreExtraField
            label={'Step'}
            onChangeFunc={onStepChange}
            onKeyDownFunc={onReturnKeyDown}
            value={query.interval || ''}
            hasTooltip={true}
            tooltipContent={
              'Time units can be used here, for example: 5s, 1m, 3h, 1d, 1y (Default if no unit is specified: s)'
            }
          />
        }
      />
        */}
      {/*
      <QueryField
        portalOrigin="ibmcloudsql"
        onChange={onQueryChange}
        //currently props.onRunQuery does not do anything
        //onRunQuery={props.onRunQuery}
        //currently props.onBlur does not do anything
        onBlur={props.onBlur}
        query={query.queryText || ''}
        placeholder="Enter a query"
      />
    */}
      <div>
        {showingHelp && (
          <>
            <h4>CloudSQL helps</h4>
            {/*<CloudSQLHelp {...props} /> */}
            <CloudSQLHelp />
          </>
        )}
      </div>
    </>
  );
}

export default memo(CloudSQLExploreQueryEditor);

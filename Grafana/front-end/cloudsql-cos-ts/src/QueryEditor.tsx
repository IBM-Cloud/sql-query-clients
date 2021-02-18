import defaults from 'lodash/defaults';

import React, { PureComponent, ChangeEvent } from 'react';
import { LegacyForms } from '@grafana/ui';
//import { Checkbox, LegacyForms } from '@grafana/ui';
//import { LegacyForms, QueryField } from '@grafana/ui';
import { QueryEditorProps, SelectableValue, HistoryItem } from '@grafana/data';
import { COSIBMDataSource } from './DataSource';
import { FORMAT_OPTIONS, CloudSQLQuery, COSIBMDataSourceOptions } from './types';
import { CloudSQLHelp } from './sql/help';

const { Select, FormField, Switch } = LegacyForms;

type Props = QueryEditorProps<COSIBMDataSource, CloudSQLQuery, COSIBMDataSourceOptions>;
//NOTE: .datasource: COSIBMDataSource
// .          .query: CloudSQLQuery
// .           (some others .data: PanelData, .exploreMode: ExploreMode, .exploreId?: any, history?: HistoryItem[])
import { CloudSQLQueryField } from './configuration/QueryFields';

export interface State {
  //default legend formatting
  // for Azure Monitor: resourceName{dimensionValue=dimensionName}.metricName
  // . ... this long formatting can be changed using aliases
  // https://grafana.com/docs/grafana/latest/features/datasources/azuremonitor/
  legendFormat: string;
  formatOption: SelectableValue<string>;
  interval: string;
  intervalFactorOption: SelectableValue<number>;
  instant: boolean;
  showingHelp: boolean;
}

export class QueryEditor extends PureComponent<Props, State> {
  onComponentDidMount() {}
  constructor(props: Props) {
    super(props);
    const { query, onChange } = props;
    if (query.get_result === undefined) {
      onChange({ ...query, get_result: true, showingHelp: false });
    }
  }

  //onQueryTextChange = (event: ChangeEvent<HTMLInputElement>) => {
  //  const { onChange, query } = this.props;
  //  onChange({ ...query, queryText: event.target.value });
  //};
  onQueryTextChange = (value: string, override?: boolean) => {
    const { query, onChange, onRunQuery } = this.props;

    if (onChange) {
      // Update the query whenever the query field changes.
      onChange({ ...query, queryText: value });

      // Run the query on Enter.
      if (override && onRunQuery) {
        onRunQuery();
      }
    }
  };

  //onConstantChange = (event: ChangeEvent<HTMLInputElement>) => {
  //  const { onChange, query, onRunQuery } = this.props;
  //  onChange({ ...query, constant: parseFloat(event.target.value) });
  //  onRunQuery(); // executes the query
  //};

  render() {
    const query = defaults(this.props.query, '');
    const ds = this.props.datasource;
    query.name = ds.name;
    query.id = ds.id;
    const props = this.props;
    //const { queryText, constant } = query;
    //const { constant } = query;
    //props.history = [];
    const no_history: Array<HistoryItem<CloudSQLQuery>> = [];

    const onTimeColumnChange = (event: ChangeEvent<HTMLInputElement>) => {
      //const { onChange, query, onRunQuery } = this.props;
      const { onChange, query } = this.props;
      onChange({ ...query, time_column: event.target.value });
      //onRunQuery(); // executes the query
    };
    const onMetricsColumnChange = (event: ChangeEvent<HTMLInputElement>) => {
      //const { onChange, query, onRunQuery } = props;
      const { onChange, query } = this.props;
      onChange({ ...query, metrics_column: event.target.value });
      //onRunQuery(); // executes the query
    };
    const onFormatChange = (option: SelectableValue<string>) => {
      const { query, onChange, onRunQuery } = this.props;
      query.format = option.value!;
      //this.setState({ formatOption: option }, this.onRunQuery);
      if (onChange) {
        const nextQuery = {
          ...query,
          format: option.value!,
        };
        onChange(nextQuery);
        //  // Update the query whenever the query field changes.
        //  onChange({ ...query, queryText: value });
        //
        onRunQuery();
      }
    };

    return (
      <>
        <div className="gf-form">
          {/*         <FormField
          width={4}
          value={constant}
          onChange={this.onConstantChange}
          label="Constant"
          type="number"
          step="0.1"
        ></FormField> */}
          <div className="display:flex gf-form">
            <FormField
              width={13}
              labelWidth={7}
              value={query.time_column}
              onChange={onTimeColumnChange}
              label="Time column"
              //tooltip="If Format is 'Time series', then type in the column name that contains the datetime data. If empty, then by default it assumes the first column is 'time', and all other columns are  'value'"
              tooltip="If Format is 'Time series', then type in the column name that contains the datetime data. If empty, then by default it assumes the first column is 'time', and the second column is 'value'"
              type="string"
            ></FormField>
            <FormField
              width={13}
              labelWidth={9}
              value={query.metrics_column}
              onChange={onMetricsColumnChange}
              label="Metrics column"
              //tooltip="If Format is 'Time series' and the SQL query returns 3-columns, then type in the column name that contains the metrics data. Each value in this column is used to group rows which become a separate time-series"
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
            />
            {/*}<Checkbox value={query.get_result} label="Get Queried Result" description="Checked means yes" onChange=/>*/}
            <Switch
              label="Get Queried Result"
              labelClass="width-10"
              checked={query.get_result}
              onChange={() => {
                const { query, onChange } = this.props;
                onChange({ ...query, get_result: !query.get_result });
              }}
              tooltip="Unchecked this if the queried data is not supposed to be returned, but is used as the source for the next one"
            />
            <Switch
              label="Show Help"
              labelClass="width-7"
              checked={query.showingHelp}
              onChange={() => {
                const { query, onChange } = this.props;
                onChange({ ...query, showingHelp: !query.showingHelp });
              }}
              tooltip="Tips on how to write the Cloud SQL query"
            />
          </div>
        </div>
        {/*
        <QueryField
          portalOrigin="ibmcloudsql"
          //labelWidth={8}
          //value={queryText || ''}
          onChange={this.onQueryTextChange}
          onRunQuery={this.props.onRunQuery}
          query={query.queryText || ''}
          //label="Query Text"
          //tooltip="Not used yet"
        ></QueryField>
        */}
        <CloudSQLQueryField
          datasource={props.datasource}
          query={props.query}
          range={props.range}
          onRunQuery={props.onRunQuery}
          onChange={props.onChange}
          onBlur={() => {}}
          history={no_history} //{props.history}
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
        <div>
          {query.showingHelp && (
            <>
              <h4>CloudSQL helps</h4>
              <CloudSQLHelp />
            </>
          )}
        </div>
      </>
    );
  }
}

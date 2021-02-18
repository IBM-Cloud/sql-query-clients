import React, { useState, SyntheticEvent } from 'react';
import { COSIBMDataSourceOptions, DataFormatTypeOptions } from '../types';
//import {
//    SelectableValue,
//    onUpdateDatasourceJsonDataOptionChecked,
//    DataSourcePluginOptionsEditorProps,
//} from '@grafana/data';
//import { EventsWithValidation, InlineFormLabel, regexValidation, LegacyForms } from '@grafana/ui';
//import { LegacyForms } from '@grafana/ui';
import { LegacyForms, useTheme, stylesFactory } from '@grafana/ui';
import { GrafanaTheme, SelectableValue } from '@grafana/data';
import { css } from 'emotion';
import defaults from 'lodash/defaults';
//import { ProgressPlugin } from 'webpack';

//const { SecretFormField, Select, Input, FormField, Switch } = LegacyForms;
const { FormField, Switch, Select } = LegacyForms;

const getStyles = stylesFactory((theme: GrafanaTheme) => ({
  infoText: css`
    padding-bottom: ${theme.spacing.md};
    color: ${theme.colors.textWeak};
  `,
  dataLink: css`
    margin-bottom: ${theme.spacing.sm};
    flex: 2;
  `,
}));

//type Props = Pick<DataSourcePluginOptionsEditorProps<COSIBMDataSourceOptions>, 'options' | 'onOptionsChange'>;
type Props = {
  value: COSIBMDataSourceOptions;
  onChange: (value: COSIBMDataSourceOptions) => void;
};

export const CloudSQLSettings = (props: Props) => {
  const { value, onChange } = props;
  const [usingTable, setUsingTable] = useState(false);

  //TODO - default setting for now
  //// can be configurable through an item in ConfigEditor.tsx
  //grafana/public/app/plugins/datasource/prometheus/configuration/PromSettings.tsx:
  defaults(value.disableMetricsLookup, true);
  defaults(value.using_table, false);
  //if (value.using_table === undefined) {
  //  defaults(value.using_table, false);
  //  onChange({
  //    ...value,
  //    ['using_table']: value.using_table,
  //  });
  //}
  //value.disableMetricsLookup = true;
  //value.using_table ?= false;

  //
  const changeHandler = (key: keyof COSIBMDataSourceOptions) => (
    event: SyntheticEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    onChange({
      ...value,
      [key]: event.currentTarget.value,
    });
  };
  const switch_changeHandler = (key: keyof COSIBMDataSourceOptions) => (
    event: SyntheticEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    onChange({
      ...value,
      [key]: !usingTable,
    });
    setUsingTable(!usingTable);
  };
  //var updateJsonData = function(jsonData: any, key: any, val: any) {
  //  jsonData[key] = val;
  //};
  //const option_changeHandler = function(key: keyof COSIBMDataSourceOptions, val: any): any {
  //  onChange({
  //    ...value,
  //    [key]: val,
  //  })
  //};
  //const onUpdateJsonDataOptionSelect = function(key: any): any {
  const option_changeHandler = (key: keyof COSIBMDataSourceOptions, item: SelectableValue<string>) => {
    props.onChange({
      ...value,
      [key]: item.value!,
    });
  };

  const theme = useTheme();
  const styles = getStyles(theme);
  return (
    <>
      <h3 className="page-heading">IBM CLoudSQL-COS-TimeSeries</h3>
      <div className="gf-form-group">
        {/*         <div className="gf-form-inline"> */}
        <div className="display:flex gf-form">
          <FormField
            className={styles.dataLink}
            label="instance CRN"
            labelWidth={8}
            type="text"
            // A bit of a hack to prevent using default value for the width from FormField
            inputWidth={null}
            value={value.instance_crn}
            onChange={changeHandler('instance_crn')}
            tooltip="SQL Query instance CRN"
            //placeholder="CRN of the SQL Query instance"
          />
        </div>
        {/*         </div> */}
        <div className="gf-form-inline">
          <div className="gf-form">
            <FormField
              label="API key"
              labelWidth={8}
              inputWidth={30}
              value={value.apiKey}
              onChange={changeHandler('apiKey')}
              tooltip="IBM Cloud API key"
              //placeholder="Cloud API key"
            />
          </div>
        </div>
        <div className="gf-form">
          <FormField
            label="COS URL target"
            labelWidth={10}
            inputWidth={30}
            value={value.target_cos_url}
            onChange={changeHandler('target_cos_url')}
            tooltip="COS URL where the queried data is stored: if 'INTO' statement is ignored or $__dest macro is used"
            //placeholder="COS URL target"
          />
        </div>
        <div className="gf-form">
          <FormField
            label="Rate limit"
            labelWidth={10}
            inputWidth={10}
            value={value.instance_rate_limit}
            onChange={changeHandler('instance_rate_limit')}
            tooltip="Max number of SQL Queries can be handled at a time"
          />
        </div>
        <div className="gf-form-inline">
          <div className="gf-form">
            <Switch
              label="Use Hive table"
              labelClass="width-10"
              checked={usingTable}
              onChange={switch_changeHandler('using_table')}
              tooltip="Select data source (to be used with $__source macro)"
            />
          </div>
        </div>
        <div className="gf-form-inline">
          {!usingTable && (
            <div className="gf-form">
              <FormField
                label="COS URL source "
                labelWidth={10}
                inputWidth={30}
                value={value.source_cos_url}
                onChange={changeHandler('source_cos_url')}
                //tooltip="COS URL where the queried data are stored"
                tooltip="(Optional) this datasource can be referenced in the query as $__source"
                //placeholder="COS URL target"
              />
              <Select
                className="width-7"
                options={DataFormatTypeOptions}
                value={DataFormatTypeOptions.find(o => o.value === value.format_type)}
                defaultValue={value.format_type}
                onChange={option => {
                  option_changeHandler('format_type', option);
                }}
              />
            </div>
          )}
          {usingTable && (
            <div className="gf-form">
              <FormField
                label="HIVE table (source)"
                labelWidth={10}
                inputWidth={30}
                value={value.table}
                onChange={changeHandler('table')}
                //tooltip="HIVE metastore reference to the source data"
                tooltip="(Optional) this datasource can be referenced in the query as $__source"
              />
            </div>
          )}
        </div>
      </div>
    </>
  );
};

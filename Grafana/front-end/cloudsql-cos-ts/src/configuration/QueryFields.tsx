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
import _ from "lodash";
import React, { ReactNode } from "react";

import { Plugin } from "slate";
import {
  ButtonCascader,
  CascaderOption,
  SlatePrism,
  TypeaheadInput,
  TypeaheadOutput,
  QueryField,
  BracesPlugin,
} from "@grafana/ui";

import Prism from "prismjs";

// dom also includes Element polyfills
//import { PromQuery, PromOptions, PromMetricsMetadata } from '../types';
import {
  CancelablePromise,
  makePromiseCancelable,
} from "../utils/CancelablePromise";
import {
  ExploreQueryFieldProps,
  QueryHint,
  //isDataFrame,
  //toLegacyResponseData,
  HistoryItem,
  AbsoluteTimeRange,
} from "@grafana/data";
import { DOMUtil, SuggestionsState } from "@grafana/ui";
import { COSIBMDataSource } from "../DataSource";
import { CloudSQLQuery, COSIBMDataSourceOptions } from "../types";

const HISTOGRAM_GROUP = "__histograms__";
const PRISM_SYNTAX = "cloudsql";
export const RECORDING_RULES_GROUP = "__recording_rules__";

function getChooserText(
  metricsLookupDisabled: boolean,
  hasSyntax: boolean,
  metrics: string[]
) {
  return "(No metrics found)";
  //if (metricsLookupDisabled) {
  //  return '(Disabled)';
  //}

  //if (!hasSyntax) {
  //  return 'Loading metrics...';
  //}

  //if (metrics && metrics.length === 0) {
  //  return '(No metrics found)';
  //}

  //return 'Metrics';
}

export function willApplySuggestion(
  suggestion: string,
  { typeaheadContext, typeaheadText }: SuggestionsState
): string {
  // Modify suggestion based on context
  switch (typeaheadContext) {
    case "context-labels": {
      const nextChar = DOMUtil.getNextCharacter();
      if (!nextChar || nextChar === "}" || nextChar === ",") {
        suggestion += "=";
      }
      break;
    }

    case "context-label-values": {
      // Always add quotes and remove existing ones instead
      if (!typeaheadText.match(/^(!?=~?"|")/)) {
        suggestion = `"${suggestion}`;
      }
      if (DOMUtil.getNextCharacter() !== '"') {
        suggestion = `${suggestion}"`;
      }
      break;
    }

    default:
  }
  return suggestion;
}

interface CloudSQLQueryFieldProps
  extends ExploreQueryFieldProps<
    COSIBMDataSource,
    CloudSQLQuery,
    COSIBMDataSourceOptions
  > {
  history: Array<HistoryItem<CloudSQLQuery>>;
  ExtraFieldElement?: ReactNode;
}

interface CloudSQLQueryFieldState {
  metricsOptions: any[];
  syntaxLoaded: boolean;
  hint: QueryHint | null;
}

export class CloudSQLQueryField extends React.PureComponent<
  CloudSQLQueryFieldProps,
  CloudSQLQueryFieldState
> {
  plugins: Plugin[];
  languageProviderInitializationPromise!: CancelablePromise<any>;

  constructor(props: CloudSQLQueryFieldProps, context: React.Context<any>) {
    super(props, context);

    this.plugins = [
      BracesPlugin(),
      SlatePrism({
        onlyIn: (node: any) => node.type === "code_block",
        //onlyIn: (node: Node) => node.object === 'block' && node.type === 'code_block',
        getSyntax: (node: any) => PRISM_SYNTAX,
      }),
    ];

    this.state = {
      metricsOptions: [],
      syntaxLoaded: false,
      hint: null,
    };
  }

  componentDidMount() {
    if (this.props.datasource.languageProvider) {
      this.refreshMetrics();
    }
    this.refreshHint();
  }

  componentWillUnmount() {
    if (this.languageProviderInitializationPromise) {
      this.languageProviderInitializationPromise.cancel();
    }
  }

  componentDidUpdate(prevProps: CloudSQLQueryFieldProps) {
    const {
      data,
      datasource: { languageProvider },
      range,
    } = this.props;

    let refreshed = false;
    if (range && prevProps.range) {
      const absoluteRange: AbsoluteTimeRange = {
        from: range.from.valueOf(),
        to: range.to.valueOf(),
      };
      const prevAbsoluteRange: AbsoluteTimeRange = {
        from: prevProps.range.from.valueOf(),
        to: prevProps.range.to.valueOf(),
      };

      if (!_.isEqual(absoluteRange, prevAbsoluteRange)) {
        this.refreshMetrics();
        refreshed = true;
      }
    }

    if (
      !refreshed &&
      languageProvider !== prevProps.datasource.languageProvider
    ) {
      this.refreshMetrics();
    }

    if (data && prevProps.data && prevProps.data.series !== data.series) {
      this.refreshHint();
    }
  }

  refreshHint = () => {
    //const { datasource, query, data } = this.props;
    const { data } = this.props;

    if (!data || data.series.length === 0) {
      this.setState({ hint: null });
      return;
    }

    //const result = isDataFrame(data.series[0]) ? data.series.map(toLegacyResponseData) : data.series;
    //TODO
    //const hints = datasource.getQueryHints(query, result);
    const hints = [];
    const hint = hints.length > 0 ? hints[0] : null;
    this.setState({ hint });
  };

  refreshMetrics = () => {
    const {
      datasource: { languageProvider },
    } = this.props;

    this.setState({
      syntaxLoaded: false,
    });

    Prism.languages[PRISM_SYNTAX] = languageProvider.syntax;
    this.languageProviderInitializationPromise = makePromiseCancelable(
      languageProvider.start()
    );
    this.languageProviderInitializationPromise.promise
      .then((remaining) => {
        remaining.map((task: Promise<any>) =>
          task.then(this.onUpdateLanguage).catch(() => {})
        );
      })
      .then(() => this.onUpdateLanguage())
      .catch((err) => {
        if (!err.isCanceled) {
          throw err;
        }
      });
  };

  onChangeMetrics = (values: string[], selectedOptions: CascaderOption[]) => {
    let query;
    if (selectedOptions.length === 1) {
      const selectedOption = selectedOptions[0];
      if (!selectedOption.children || selectedOption.children.length === 0) {
        query = selectedOption.value;
      } else {
        // Ignore click on group
        return;
      }
    } else {
      const prefix = selectedOptions[0].value;
      const metric = selectedOptions[1].value;
      if (prefix === HISTOGRAM_GROUP) {
        query = `histogram_quantile(0.95, sum(rate(${metric}[5m])) by (le))`;
      } else {
        query = metric;
      }
    }
    this.onChangeQuery(query, true);
  };

  onChangeQuery = (value: string, override?: boolean) => {
    // Send text change to parent
    const { query, onChange, onRunQuery } = this.props;
    if (onChange) {
      //const nextQuery: CloudSQLQuery = { ...query, expr: value };
      const nextQuery: CloudSQLQuery = { ...query, queryText: value };
      onChange(nextQuery);

      if (override && onRunQuery) {
        onRunQuery();
      }
    }
  };

  onClickHintFix = () => {
    //const { datasource, query, onChange, onRunQuery } = this.props;
    const { onRunQuery } = this.props;
    //const { hint } = this.state;

    //TODO
    //onChange(datasource.modifyQuery(query, hint!.fix!.action));
    onRunQuery();
  };

  onUpdateLanguage = () => {
    const {
      //datasource,
      datasource: { languageProvider },
    } = this.props;
    //const { histogramMetrics, metrics, metricsMetadata, lookupMetricsThreshold } = languageProvider;
    const { histogramMetrics, metrics } = languageProvider;

    if (!metrics) {
      return;
    }

    //TODO
    // Build metrics tree
    //const metricsByPrefix = groupMetricsByPrefix(metrics, metricsMetadata);
    const metricsByPrefix = [""];

    let metricsOptions;
    if (histogramMetrics) {
      const histogramOptions = histogramMetrics.map((hm: any) => ({
        label: hm,
        value: hm,
      }));
      metricsOptions =
        histogramMetrics.length > 0
          ? [
              {
                label: "Histograms",
                value: HISTOGRAM_GROUP,
                children: histogramOptions,
                isLeaf: false,
              },
              ...metricsByPrefix,
            ]
          : metricsByPrefix;
    }

    // Hint for big disabled lookups
    let hint: QueryHint | null = null;

    //TODO
    //if (!datasource.lookupsDisabled && languageProvider.lookupsDisabled) {
    //  hint = {
    //    label: `Dynamic label lookup is disabled for datasources with more than ${lookupMetricsThreshold} metrics.`,
    //    type: 'INFO',
    //  };
    //}

    this.setState({ hint, metricsOptions, syntaxLoaded: true });
  };

  onTypeahead = async (typeahead: TypeaheadInput): Promise<TypeaheadOutput> => {
    const {
      datasource: { languageProvider },
    } = this.props;

    if (!languageProvider) {
      return { suggestions: [] };
    }

    const { history } = this.props;
    const { prefix, text, value, wrapperClasses, labelKey } = typeahead;

    const result = await languageProvider.provideCompletionItems(
      { text, value, prefix, wrapperClasses, labelKey },
      { history }
    );

    // console.log('handleTypeahead', wrapperClasses, text, prefix, labelKey, result.context);

    return result;
  };

  render() {
    const {
      datasource,
      datasource: { languageProvider },
      query,
      ExtraFieldElement,
    } = this.props;
    const { metricsOptions, syntaxLoaded, hint } = this.state;
    const cleanText = languageProvider ? languageProvider.cleanText : undefined;
    //TODO
    const chooserText = getChooserText(
      datasource.lookupsDisabled,
      syntaxLoaded,
      metricsOptions
    );
    //const chooserText = '';
    const buttonDisabled = !(
      syntaxLoaded &&
      metricsOptions &&
      metricsOptions.length > 0
    );

    return (
      <>
        <div className="gf-form-inline gf-form-inline--xs-view-flex-column flex-grow-1">
          <div className="gf-form flex-shrink-0 min-width-5">
            <ButtonCascader
              options={metricsOptions}
              disabled={buttonDisabled}
              onChange={this.onChangeMetrics}
            >
              {chooserText}
            </ButtonCascader>
          </div>
          <div className="gf-form gf-form--grow flex-shrink-1 min-width-15">
            <QueryField
              additionalPlugins={this.plugins}
              cleanText={cleanText}
              query={query.queryText || ""}
              //query={query.expr}
              onTypeahead={this.onTypeahead}
              onWillApplySuggestion={willApplySuggestion}
              onBlur={this.props.onBlur}
              onChange={this.onChangeQuery}
              onRunQuery={this.props.onRunQuery}
              placeholder="Enter a CloudSQL query (run with Shift+Enter)"
              portalOrigin="ibmcloudsql"
              syntaxLoaded={syntaxLoaded}
            />
          </div>
          {ExtraFieldElement}
        </div>
        {hint ? (
          <div className="query-row-break">
            <div className="prom-query-field-info text-warning">
              {hint.label}{" "}
              {hint.fix ? (
                <a className="text-link muted" onClick={this.onClickHintFix}>
                  {hint.fix.label}
                </a>
              ) : null}
            </div>
          </div>
        ) : null}
      </>
    );
  }
}

export default CloudSQLQueryField;

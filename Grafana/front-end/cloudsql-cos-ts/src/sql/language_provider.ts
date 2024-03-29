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
import LRU from "lru-cache";
import { Value } from "slate";

import { dateTime, LanguageProvider, HistoryItem } from "@grafana/data";
import {
  CompletionItem,
  TypeaheadInput,
  TypeaheadOutput,
  CompletionItemGroup,
} from "@grafana/ui";

import {
  parseSelector,
  processLabels,
  processHistogramLabels,
  fixSummariesMetadata,
} from "./language_utils";
import CloudSQLSyntax, { KEYWORDS, FUNCTIONS, RATE_RANGES } from "./cloudsql";

import { COSIBMDataSource } from "../DataSource";
import { CloudSQLQuery, CloudSQLMetricsMetadata } from "../types";

const DEFAULT_KEYS = ["job", "instance"];
const EMPTY_SELECTOR = "{}";
const HISTORY_ITEM_COUNT = 5; //number of historical element to take
const HISTORY_COUNT_CUTOFF = 1000 * 60 * 60 * 24; // 24h
export const DEFAULT_LOOKUP_METRICS_THRESHOLD = 10000; // number of metrics defining an installation that's too big

//const wrapLabel = (h: string): CompletionItem => (<CompletionItem>{label: h});
function wrapLabel(h: string): CompletionItem {
  return { label: h } as CompletionItem;
}

// configure a kind
const setFunctionKind = (suggestion: CompletionItem): CompletionItem => {
  suggestion.kind = "function";
  if (suggestion.detail) {
    suggestion.documentation += ". Example: \n " + suggestion.detail;
  }
  return suggestion;
};
const setKeywordKind = (suggestion: CompletionItem): CompletionItem => {
  suggestion.kind = "keyword";
  //suggestion.kind = 'function';
  if (suggestion.detail) {
    suggestion.documentation += ". Example: \n " + suggestion.detail;
  }
  return suggestion;
};

export function addHistoryMetadata(
  item: CompletionItem,
  history: any[]
): CompletionItem {
  const cutoffTs = Date.now() - HISTORY_COUNT_CUTOFF;
  const historyForItem = history.filter(
    (h) => h.ts > cutoffTs && h.query === item.label
  );
  const count = historyForItem.length;
  const recent = historyForItem[0];
  let hint = `Queried ${count} times in the last 24h.`;

  if (recent) {
    const lastQueried = dateTime(recent.ts).fromNow();
    hint = `${hint} Last queried ${lastQueried}.`;
  }

  return {
    ...item,
    documentation: hint,
  };
}

function addMetricsMetadata(
  metric: string,
  metadata?: CloudSQLMetricsMetadata
): CompletionItem {
  const item: CompletionItem = { label: metric };
  if (metadata && metadata[metric]) {
    const { type, help } = metadata[metric][0];
    item.documentation = `${type.toUpperCase()}: ${help}`;
  }
  return item;
}

const PREFIX_DELIMITER_REGEX = /(="|!="|=~"|!~"|\{|\[|\(|\+|-|\/|\*|%|\^|\band\b|\bor\b|\bunless\b|==|>=|!=|<=|>|<|=|~|,)/;

export default class CloudSQLLanguageProvider extends LanguageProvider {
  histogramMetrics?: string[];
  timeRange?: { start: number; end: number };
  metrics?: string[];
  metricsMetadata?: CloudSQLMetricsMetadata;
  startTask!: Promise<any>;
  datasource: COSIBMDataSource;
  lookupMetricsThreshold: number;
  lookupsDisabled: boolean; // Dynamically set to true for big/slow instances

  /**
   *  Cache for labels of series. This is bit simplistic in the sense that it just counts responses each as a 1 and does
   *  not account for different size of a response. If that is needed a `length` function can be added in the options.
   *  10 as a max size is totally arbitrary right now.
   */
  private labelsCache = new LRU<string, Record<string, string[]>>(10);

  constructor(
    datasource: COSIBMDataSource,
    initialValues?: Partial<CloudSQLLanguageProvider>
  ) {
    super();

    this.datasource = datasource;
    this.histogramMetrics = [];
    this.timeRange = { start: 0, end: 0 };
    this.metrics = [];
    // Disable lookups until we know the instance is small enough
    this.lookupMetricsThreshold = DEFAULT_LOOKUP_METRICS_THRESHOLD;
    this.lookupsDisabled = true;

    Object.assign(this, initialValues);
  }

  // Strip syntax chars so that typeahead suggestions can work on clean inputs
  cleanText(s: string): string {
    const parts = s.split(PREFIX_DELIMITER_REGEX);
    const last = parts.pop();
    if (last) {
      return last.trimLeft().replace(/"$/, "").replace(/^"/, "");
    } else {
      return s;
    }
  }

  get syntax() {
    return CloudSQLSyntax;
  }

  request = async (url: string, defaultValue: any): Promise<any> => {
    try {
      //TODO
      //const res = await this.datasource.metadataRequest(url);
      //const body = await (res.data || res.json());
      //return body.data;
      throw new Error("TODO error");
    } catch (error) {
      console.error(error);
    }

    return defaultValue;
  };

  start = async (): Promise<any[]> => {
    if (this.datasource.lookupsDisabled) {
      return [];
    }

    this.metrics = await this.request("/api/v1/label/__name__/values", []);
    //TODO
    //this.lookupsDisabled = this.metrics.length > this.lookupMetricsThreshold;
    this.metricsMetadata = fixSummariesMetadata(
      await this.request("/api/v1/metadata", {})
    );
    this.processHistogramMetrics(this.metrics || []);

    return [];
  };

  processHistogramMetrics = (data: string[]) => {
    const { values } = processHistogramLabels(data);

    if (values && values["__name__"]) {
      this.histogramMetrics = values["__name__"].slice().sort();
    }
  };

  //  NOTE: this one returns list of suggestions
  //  const result = await languageProvider.provideCompletionItems(
  //    { text, value, prefix, wrapperClasses, labelKey },
  //    { history }
  //  );
  provideCompletionItems = async (
    { prefix, text, value, labelKey, wrapperClasses }: TypeaheadInput,
    context: { history: Array<HistoryItem<CloudSQLQuery>> } = { history: [] }
  ): Promise<TypeaheadOutput> => {
    // Local text properties
    const empty = value?.document?.text?.length === 0;
    const selectedLines = value?.document?.getTextsAtRange(value.selection);
    const currentLine =
      selectedLines?.size === 1 ? selectedLines.first().getText() : null;
    let nextCharacter;
    if (value?.selection?.anchor.offset) {
      nextCharacter = currentLine
        ? currentLine[value.selection.anchor.offset]
        : null;
    } else {
      nextCharacter = null;
    }
    // Syntax spans have 3 classes by default. More indicate a recognized token
    const tokenRecognized = wrapperClasses.length > 3;
    // Non-empty prefix, but not inside known token
    const prefixUnrecognized = prefix && !tokenRecognized;

    // Prevent suggestions in `function(|suffix)`
    const noSuffix = !nextCharacter || nextCharacter === ")";

    // Prefix is safe if it does not immediately follow a complete expression and has no text after it
    const safePrefix = prefix && !text.match(/^[\]})\s]+$/) && noSuffix;

    // About to type next operand if preceded by binary operator
    const operatorsPattern = /[+\-*/^%]/;
    const isNextOperand = text.match(operatorsPattern);

    // Determine candidates by CSS context
    if (wrapperClasses.includes("context-range")) {
      // Suggestions for metric[|]
      return this.getRangeCompletionItems();
    } else if (wrapperClasses.includes("context-labels")) {
      // Suggestions for metric{|} and metric{foo=|}, as well as metric-independent label queries like {|}
      return this.getLabelCompletionItems({
        prefix,
        text,
        value,
        labelKey,
        wrapperClasses,
      });
    } else if (wrapperClasses.includes("context-aggregation") && value) {
      // Suggestions for sum(metric) by (|)
      return this.getAggregationCompletionItems(value);
    } else if (empty) {
      // Suggestions for empty query field
      return this.getEmptyCompletionItems(context);
    } else if (prefixUnrecognized && noSuffix && !isNextOperand) {
      // Show term suggestions in a couple of scenarios
      return this.getBeginningCompletionItems(context);
    } else if (prefixUnrecognized && safePrefix) {
      // Show term suggestions in a couple of scenarios
      return this.getTermCompletionItems();
    }

    return {
      suggestions: [],
    };
  };

  getBeginningCompletionItems = (context: {
    history: Array<HistoryItem<CloudSQLQuery>>;
  }): TypeaheadOutput => {
    return {
      suggestions: [
        ...this.getEmptyCompletionItems(context).suggestions,
        ...this.getTermCompletionItems().suggestions,
      ],
    };
  };

  getEmptyCompletionItems = (context: {
    history: Array<HistoryItem<CloudSQLQuery>>;
  }): TypeaheadOutput => {
    const { history } = context;
    interface Suggestion {
      prefixMatch?: boolean;
      skipSort: boolean;
      label: string;
      items: any;
    }
    const suggestions: Suggestion[] = [];

    if (history && history.length) {
      const historyItems = _.chain(history)
        .map((h) => h.query.queryText)
        .filter()
        .uniq()
        .take(HISTORY_ITEM_COUNT)
        //.map(wrapLabel)
        .map((h) => {
          return { label: h } as CompletionItem;
        })
        .map((item) => addHistoryMetadata(item, history))
        .value();

      suggestions.push({
        prefixMatch: true,
        skipSort: true,
        label: "History",
        items: historyItems,
      });
    }

    return { suggestions };
  };

  getTermCompletionItems = (): TypeaheadOutput => {
    const { metrics, metricsMetadata } = this;
    interface Suggestion {
      prefixMatch?: boolean;
      label: string;
      items: any;
    }
    const suggestions: Suggestion[] = [];

    //CompletionItemGroup
    suggestions.push({
      prefixMatch: true,
      label: "Functions",
      items: FUNCTIONS.map(setFunctionKind),
    });
    suggestions.push({
      prefixMatch: true,
      label: "Clauses",
      items: KEYWORDS.map(setKeywordKind),
    });

    if (metrics && metrics.length) {
      suggestions.push({
        label: "Metrics",
        items: metrics.map((m) => addMetricsMetadata(m, metricsMetadata)),
      });
    }

    return { suggestions };
  };

  getRangeCompletionItems(): TypeaheadOutput {
    return {
      context: "context-range",
      suggestions: [
        {
          label: "Range vector",
          items: [...RATE_RANGES],
        },
      ],
    };
  }

  getAggregationCompletionItems = async (
    value: Value
  ): Promise<TypeaheadOutput> => {
    const suggestions: CompletionItemGroup[] = [];

    // Stitch all query lines together to support multi-line queries
    let queryOffset;
    const queryText = value.document
      .getBlocks()
      .reduce((text: string | undefined, block) => {
        const blockText = block?.getText();
        if (text === undefined) {
          text = "";
        }
        if (value.anchorBlock?.key === block?.key) {
          // Newline characters are not accounted for but this is irrelevant
          // for the purpose of extracting the selector string
          queryOffset = value.selection.anchor.offset + text.length;
        }

        return text + blockText;
      }, "");

    // Try search for selector part on the left-hand side, such as `sum (m) by (l)`
    const openParensAggregationIndex = queryText.lastIndexOf("(", queryOffset);
    let openParensSelectorIndex = queryText.lastIndexOf(
      "(",
      openParensAggregationIndex - 1
    );
    let closeParensSelectorIndex = queryText.indexOf(
      ")",
      openParensSelectorIndex
    );

    // Try search for selector part of an alternate aggregation clause, such as `sum by (l) (m)`
    if (openParensSelectorIndex === -1) {
      const closeParensAggregationIndex = queryText.indexOf(")", queryOffset);
      closeParensSelectorIndex = queryText.indexOf(
        ")",
        closeParensAggregationIndex + 1
      );
      openParensSelectorIndex = queryText.lastIndexOf(
        "(",
        closeParensSelectorIndex
      );
    }

    const result = {
      suggestions,
      context: "context-aggregation",
    };

    // Suggestions are useless for alternative aggregation clauses without a selector in context
    if (openParensSelectorIndex === -1) {
      return result;
    }

    // Range vector syntax not accounted for by subsequent parse so discard it if present
    const selectorString = queryText
      .slice(openParensSelectorIndex + 1, closeParensSelectorIndex)
      .replace(/\[[^\]]+\]$/, "");

    const selector = parseSelector(selectorString, selectorString.length - 2)
      .selector;

    const labelValues = await this.getLabelValues(selector);
    if (labelValues) {
      suggestions.push({
        label: "Labels",
        items: Object.keys(labelValues).map(wrapLabel),
      });
      //suggestions.push({ label: 'Labels', items: Object.keys(labelValues).map(h => (<CompletionItem>{label:h})) });
    }
    return result;
  };

  getLabelCompletionItems = async ({
    text,
    wrapperClasses,
    labelKey,
    value,
  }: TypeaheadInput): Promise<TypeaheadOutput> => {
    const suggestions: CompletionItemGroup[] = [];
    const line = value?.anchorBlock?.getText();
    const cursorOffset = value?.selection?.anchor?.offset || 0;
    const suffix = line?.substr(cursorOffset);
    const prefix = line?.substr(0, cursorOffset);
    const isValueStart = text.match(/^(=|=~|!=|!~)/);
    const isValueEnd = suffix?.match(/^"?[,}]/);
    // detect cursor in front of value, e.g., {key=|"}
    const isPreValue = prefix?.match(/(=|=~|!=|!~)$/) && suffix?.match(/^"/);

    // Don't suggestq anything at the beginning or inside a value
    const isValueEmpty = isValueStart && isValueEnd;
    const hasValuePrefix = isValueEnd && !isValueStart;
    if ((!isValueEmpty && !hasValuePrefix) || isPreValue) {
      return { suggestions };
    }

    // Get normalized selector
    let selector;
    let parsedSelector; // { labelKeys: any[]; selector: string };
    try {
      parsedSelector = parseSelector(line || "", cursorOffset);
      selector = parsedSelector.selector;
    } catch {
      selector = EMPTY_SELECTOR;
    }

    const containsMetric = selector.includes("__name__=");
    const existingKeys = parsedSelector ? parsedSelector.labelKeys : [];

    let labelValues;
    // Query labels for selector
    if (selector) {
      labelValues = await this.getLabelValues(selector, !containsMetric);
    }

    if (!labelValues) {
      console.warn(
        `Server did not return any values for selector = ${selector}`
      );
      return { suggestions };
    }

    let context = "";
    if ((text && isValueStart) || wrapperClasses.includes("attr-value")) {
      // Label values
      if (labelKey && labelValues[labelKey]) {
        context = "context-label-values";
        suggestions.push({
          label: `Label values for "${labelKey}"`,
          items: labelValues[labelKey].map(wrapLabel),
          //items: labelValues[labelKey].map(h => (<CompletionItem>{label:h})) ,
        });
      }
    } else {
      // Label keys
      const labelKeys = labelValues
        ? Object.keys(labelValues)
        : containsMetric
        ? null
        : DEFAULT_KEYS;

      if (labelKeys) {
        const possibleKeys = _.difference(labelKeys, existingKeys);
        if (possibleKeys.length) {
          context = "context-labels";
          const newItems = possibleKeys.map((key) => ({ label: key }));
          const newSuggestion: CompletionItemGroup = {
            label: `Labels`,
            items: newItems,
          };
          suggestions.push(newSuggestion);
        }
      }
    }

    return { context, suggestions };
  };

  async getLabelValues(selector: string, withName?: boolean) {
    if (this.lookupsDisabled) {
      return undefined;
    }
    try {
      if (selector === EMPTY_SELECTOR) {
        return await this.fetchDefaultLabels();
      } else {
        return await this.fetchSeriesLabels(selector, withName);
      }
    } catch (error) {
      // TODO: better error handling
      console.error(error);
      return undefined;
    }
  }

  fetchLabelValues = async (key: string): Promise<Record<string, string[]>> => {
    const data = await this.request(`/api/v1/label/${key}/values`, []);
    return { [key]: data };
  };

  roundToMinutes(seconds: number): number {
    return Math.floor(seconds / 60);
  }

  /**
   * Fetch labels for a series. This is cached by it's args but also by the global timeRange currently selected as
   * they can change over requested time.
   * @param name
   * @param withName
   */
  fetchSeriesLabels = async (
    name: string,
    withName?: boolean
  ): Promise<Record<string, string[]>> => {
    //const tRange = this.datasource.getTimeRange();
    const tRange = { start: 0, end: 1 }; //TODO remove this
    const params = new URLSearchParams({
      "match[]": name,
      start: tRange["start"].toString(),
      end: tRange["end"].toString(),
    });
    const url = `/api/v1/series?${params.toString()}`;
    // Cache key is a bit different here. We add the `withName` param and also round up to a minute the intervals.
    // The rounding may seem strange but makes relative intervals like now-1h less prone to need separate request every
    // millisecond while still actually getting all the keys for the correct interval. This still can create problems
    // when user does not the newest values for a minute if already cached.
    params.set("start", this.roundToMinutes(tRange["start"]).toString());
    params.set("end", this.roundToMinutes(tRange["end"]).toString());
    params.append("withName", withName ? "true" : "false");
    const cacheKey = `/api/v1/series?${params.toString()}`;
    let value = this.labelsCache.get(cacheKey);
    if (!value) {
      const data = await this.request(url, []);
      const { values } = processLabels(data, withName);
      value = values;
      this.labelsCache.set(cacheKey, value);
    }
    return value;
  };

  /**
   * Fetch this only one as we assume this won't change over time. This is cached differently from fetchSeriesLabels
   * because we can cache more aggressively here and also we do not want to invalidate this cache the same way as in
   * fetchSeriesLabels.
   */
  fetchDefaultLabels = _.once(async () => {
    const values = await Promise.all(
      DEFAULT_KEYS.map((key) => this.fetchLabelValues(key))
    );
    return values.reduce((acc, value) => ({ ...acc, ...value }), {});
  });
}

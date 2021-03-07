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
import React from "react";
import { ExploreStartPageProps, DataQuery } from "@grafana/data";
import { stripIndent, stripIndents } from "common-tags";
import { css, cx } from "emotion";

interface QueryExampleCat {
  category: string;
  examples: Array<{
    title: string;
    queryText: string;
    format?: string;
    time_column?: string;
    metrics_column?: string;
  }>;
}
//interface QueryExample {
//  title: string;
//  label: string;
//  expression?: string;
//}

const SQLQUERY_EXAMPLES: QueryExampleCat[] = [
  {
    category: "Time-Series",
    examples: [
      {
        title:
          "Return single time-series [replace COS_IN_URL, update format, and column names (field_name, time_stamp, observation) to match those in your data]",
        format: "time_series",
        time_column: "tt",
        queryText: stripIndents`WITH container_ts_table AS
  (SELECT field_name,
          ts
   FROM <COS_IN_URL> STORED AS PARQUET USING TIME_SERIES_FORMAT(KEY="field_name", timetick="time_stamp", value="observation") IN ts),
 tmp_table AS
(
SELECT field_name AS user_agent,
       ts_explode(ts_seg_sum(TS_SEGMENT_BY_TIME(ts, 604800000, 604800000))) AS (tt,
                                                                                value)
FROM container_ts_table)
 SELECT tt, log(value) as value
FROM tmp_table
WHERE user_agent LIKE "<a-value-in-column"
INTO <COS_OUT_URL> STORED AS PARQUET`,
      },
      {
        title:
          "Return multiple time-series [replace COS_IN_URL, update format, and column names (field_name, time_stamp, observation) to match those in your data]",
        format: "time_series",
        time_column: "tt",
        metrics_column: "user_agent",
        queryText: stripIndents`WITH container_ts_table AS
  (SELECT field_name,
          ts
   FROM <COS_IN_URL> STORED AS PARQUET USING TIME_SERIES_FORMAT(KEY="field_name", timetick="time_stamp", value="observation") IN ts),
 tmp_table AS
(
SELECT field_name AS user_agent,
       ts_explode(ts_seg_sum(TS_SEGMENT_BY_TIME(ts, 604800000, 604800000))) AS (tt,
                                                                                value)
FROM container_ts_table)
 SELECT tt, log(value) as value
FROM tmp_table
INTO <COS_OUT_URL> STORED AS PARQUET`,
      },
    ],
  },
  {
    category: "Table",
    examples: [
      {
        title: "Return a table-form data",
        format: "table",
        queryText: stripIndents`WITH container_ts_table AS
  (SELECT field_name, ts
   FROM <COS_IN_URL> STORED AS PARQUET USING TIME_SERIES_FORMAT(KEY="field_name", timetick="time_stamp", value="observation") IN ts)
SELECT field_name AS user_agent,
       ts_explode(ts_seg_sum(TS_SEGMENT_BY_TIME(ts, 604800000, 604800000))) AS (tt, value)
FROM container_ts_table INTO <COS_OUT_URL> STORED AS PARQUET`,
      },
    ],
  },
];

function renderHighlightedMarkup(code: string, keyPrefix: string) {
  const spans = code;
  return <div className="slate-query-field">{spans}</div>;
}

//https://github.com/grafana/grafana/blob/376a9d35e4da9cd21040d55d6b2280f102b38a4e/public/sass/pages/_explore.scss
const exampleCategory = css`
  margin-top: 5px;
`;

const cheatsheetitem = css`
  margin: $space-lg 0;
`;

const cheatsheetitem__title = css`
  font-size: $font-size-h3;
`;

const cheatsheetitem__example = css`
  margin: $space-xs 0;
  cursor: pointer;
`;

export default class CheatSheet extends React.PureComponent<
  ExploreStartPageProps,
  { userExamples: string[] }
> {
  renderExpression(
    expr: string,
    keyPrefix: string,
    format: string,
    time_column: string,
    metrics_column: string
  ) {
    const { onClickExample } = this.props;

    return (
      <div
        //className="cheat-sheet-item__example"
        className={cx(cheatsheetitem__example)}
        key={expr}
        onClick={(e) =>
          onClickExample({
            refId: "A",
            queryText: expr,
            format: format,
            time_column: time_column,
            metrics_column: metrics_column,
          } as DataQuery)
        }
      >
        <pre>{renderHighlightedMarkup(expr, keyPrefix)}</pre>
      </div>
    );
  }
  render() {
    return (
      <div>
        <h2>CloudSQL Cheat Sheet</h2>
        {SQLQUERY_EXAMPLES.map((cat, j) => (
          <div key={`cat-${j}`}>
            <div className={cx(cheatsheetitem__title, exampleCategory)}>
              {cat.category}
            </div>
            {cat.examples.map((item, i) => (
              <div className={cx(cheatsheetitem)} key={`item-${i}`}>
                <h4>{item.title}</h4>
                {this.renderExpression(
                  item.queryText,
                  `item-${i}`,
                  item.format | "",
                  item.time_column | "",
                  item.metrics_column | ""
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    );
  }
}

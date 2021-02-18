import React from 'react';
import { ExploreStartPageProps, DataQuery } from '@grafana/data';
import { stripIndent, stripIndents } from 'common-tags';
//import { flattenTokens } from '@grafana/ui/src/slate-plugins/slate-prism';
//import { flattenTokens } from '@grafana/ui';
import { css, cx } from 'emotion';

interface QueryExampleCat {
  category: string;
  examples: Array<{
    title: string;
    expr: string;
  }>;
}
//interface QueryExample {
//  title: string;
//  label: string;
//  expression?: string;
//}

const CLIQ_EXAMPLES: QueryExampleCat[] = [
  {
    category: 'Lambda',
    examples: [
      {
        title: 'View latency statistics for 5-minute intervals',
        expr: stripIndents`filter @type = "REPORT" |
                         stats avg(@duration), max(@duration), min(@duration) by bin(5m)`,
      },
      {
        title: 'Determine the amount of overprovisioned memory',
        expr: stripIndent`
      filter @type = "REPORT" |
      stats max(@memorySize / 1024 / 1024) as provisonedMemoryMB,
            min(@maxMemoryUsed / 1024 / 1024) as smallestMemoryRequestMB,
            avg(@maxMemoryUsed / 1024 / 1024) as avgMemoryUsedMB,
            max(@maxMemoryUsed / 1024 / 1024) as maxMemoryUsedMB,
            provisonedMemoryMB - maxMemoryUsedMB as overProvisionedMB`,
      },
      {
        title: 'Find the most expensive requests',
        expr: stripIndents`filter @type = "REPORT" |
                         fields @requestId, @billedDuration |
                         sort by @billedDuration desc`,
      },
    ],
  },
];
//const CHEAT_SHEET_ITEMS: QueryExample[] = [
//  {
//    title: 'Getting started',
//    label:
//      'Start by selecting a measurement and field from the dropdown above. You can then use the tag selector to further narrow your search.',
//  },
//  {
//    title: 'Request Rate',
//    expression: 'rate(http_request_total[5m])',
//    label:
//      'Given an HTTP request counter, this query calculates the per-second average request rate over the last 5 minutes.',
//  },
//  {
//    title: '95th Percentile of Request Latencies',
//    expression: 'histogram_quantile(0.95, sum(rate(prometheus_http_request_duration_seconds_bucket[5m])) by (le))',
//    label: 'Calculates the 95th percentile of HTTP request rate over 5 minute windows.',
//  },
//  {
//    title: 'Alerts Firing',
//    expression: 'sort_desc(sum(sum_over_time(ALERTS{alertstate="firing"}[24h])) by (alertname))',
//    label: 'Sums up the alerts that have been firing over the last 24 hours.',
//  },
//  {
//    title: 'Step',
//    label:
//      'Defines the graph resolution using a duration format (15s, 1m, 3h, ...). Small steps create high-resolution graphs but can be slow over larger time ranges. Using a longer step lowers the resolution and smooths the graph by producing fewer datapoints. If no step is given the resolution is calculated automatically.',
//  },
//];

function renderHighlightedMarkup(code: string, keyPrefix: string) {
  const spans = code;
  //const grammar = Prism.languages['cloudwatch'] ?? tokenizer;
  //const tokens = flattenTokens(Prism.tokenize(code, grammar));
  //const spans = tokens
  //  .filter(token => typeof token !== 'string')
  //  .map((token, i) => {
  //    return (
  //      <span
  //        className={`prism-token token ${token.types.join(' ')} ${token.aliases.join(' ')}`}
  //        key={`${keyPrefix}-token-${i}`}
  //      >
  //        {token.content}
  //      </span>
  //    );
  //  });
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

//export default class LogsCheatSheet extends PureComponent<ExploreStartPageProps, { userExamples: string[] }>
//export default (props: ExploreStartPageProps) => (
//CheatSheet(props: ExploreStartPageProps)
export default class CheatSheet extends React.PureComponent<ExploreStartPageProps, { userExamples: string[] }> {
  renderExpression(expr: string, keyPrefix: string) {
    const { onClickExample } = this.props;

    return (
      <div
        //className="cheat-sheet-item__example"
        className={cx(cheatsheetitem__example)}
        key={expr}
        onClick={e => onClickExample({ refId: 'A', expression: expr } as DataQuery)}
      >
        <pre>{renderHighlightedMarkup(expr, keyPrefix)}</pre>
      </div>
    );
  }
  render() {
    return (
      <div>
        <h2>CloudSQL Cheat Sheet</h2>
        {CLIQ_EXAMPLES.map((cat, j) => (
          <div key={`cat-${j}`}>
            <div className={cx(cheatsheetitem__title, exampleCategory)}>{cat.category}</div>
            {cat.examples.map((item, i) => (
              <div className={cx(cheatsheetitem)} key={`item-${i}`}>
                <h4>{item.title}</h4>
                {this.renderExpression(item.expr, `item-${i}`)}
              </div>
            ))}
          </div>
        ))}
      </div>
    );
    //return (
    //  <div>
    //    <h2>CloudSQL Cheat Sheet</h2>
    //    {CHEAT_SHEET_ITEMS.map((item, index) => (
    //      <div className="cheat-sheet-item" key={index}>
    //        <div className="cheat-sheet-item__title">{item.title}</div>
    //        {item.expression ? (
    //          <div
    //            className="cheat-sheet-item__example"
    //            onClick={e => props.onClickExample({ refId: 'A', expr: item.expression } as DataQuery)}
    //          >
    //            <code>{item.expression}</code>
    //          </div>
    //        ) : null}
    //        <div className="cheat-sheet-item__label">{item.label}</div>
    //      </div>
    //    ))}
    //  </div>
    //);
  }
}
//);

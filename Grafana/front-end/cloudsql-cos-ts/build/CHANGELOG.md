#### 0.4.0 (2021-04-07)

##### Release Hightlights front-end

* support macros: $__timeFilter, $__timeFilter(string), $__timeFilter(col-name, [type]), $__source, $__dest ($__dest(csv), $__dest()), $__source_prev(query-refId)
* returned data, in either `table` and `time-series` form, is now converted to DataFrame
* adding data source location is optional at plugin instance creation time
* adding data destination location is optional at plugin instance creation time
* a query can be configured as an intermediate for the next queries, i.e. no returned data is needed.
* syntax highlighting support in query editor

##### Other Changes/Improvements

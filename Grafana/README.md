# Grafana IBM SQL Query Connector


Overview
-----------

This is a community based IBM SQL Query Grafana connector. The connector has 2 parts: a front-end part and back-end part.
The plugin provides the capability to launch one or many SQL-based queries to the CloudSQL service instance. The returned data can be categorized into either: TimeSeries or Table.
With TimeSeries, there must be a column holding timestamp data, and a column holding observation/measurement data. With Multi-TimeSeries, there must be a third column as metrics.

A tutorial is available at [IBM Cloud's Blog](https://www.ibm.com/cloud/blog/time-series-analytics-for-ibm-virtual-private-cloud-flows-using-grafana)

What is Grafana?
-----------

Grafana is a multi-platform open source analytics and interactive visualization web application. It provides charts, graphs, and alerts for the web when connected to supported data sources.


Usage
-----------

### Setup

1. The plugin can be built using

```console
yarn
yarn dev
```

2. Grafana 7.4+ should be downloaded and we put the the built code into the designated plugin location of Grafana

Suppose you download Grafana to
```console
export GRAFANA_DIR = $HOME/go/src/github.com/grafana/grafana
```
then

```console
cp -R <path/to>/sql-query-clients/Grafana/front-end/cloudsql-cos-ts/dist $GRAFANA_DIR/plugins-bundled/cloudsql-cos-ts
```

### Launch Grafana

Open a new console and run

```console
$GRAFANA_DIR/bin/grafana-server
```

### Launch back-end

Open a new console and run
```console
# ONLY ONCE
cd <path/to>/sql-query-clients/Grafana/back-end/
conda env create -f environment.yml

# EACH TIME the back-end is run
conda activate cloudsql_cos_ts
python app.py
```


### Creating a new IBM SQL Query Source

The plugin is named `cloudsql-cos-ts`. There, we need to configure the IP:port of the backend webapp, and the credential required to connect to your
CloudSQL service instance.


## Development

Building and Installation
-----------

0. Download Grafana 7.4+

```console
wget https://dl.grafana.com/oss/release/grafana-7.4.1.linux-amd64.tar.gz
tar -zxvf grafana-7.4.1.linux-amd64.tar.gz
ln -s grafana grafana-7.4.1
```
1. Edit the file

```console
vi $GRAFANA_DIR/conf/custom.ini
```
and update the `app_mode` to
```console
app_mode = development
```
and chosoe the location to your plugin via the `plugins` line
```console
plugins = <path/to>/sql-query-clients/Grafana/front-end
```

2. Compile the plugin after changed

```console
yarn dev
```

3. Reload the web-browser for the change to plugin is updated.

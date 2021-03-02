/*
 * Copyright (C) 2017-2019 Dremio Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package com.dremio.exec.store.jdbc.conf;
import static com.google.common.base.Preconditions.checkNotNull;
import com.dremio.exec.store.jdbc.*;
import com.dremio.options.OptionManager;
import com.dremio.security.CredentialsService;
import org.apache.log4j.Logger;
import com.dremio.exec.catalog.conf.DisplayMetadata;
import com.dremio.exec.catalog.conf.NotMetadataImpacting;
import com.dremio.exec.catalog.conf.Secret;
import com.dremio.exec.catalog.conf.SourceType;
import com.dremio.exec.store.jdbc.JdbcPluginConfig;
import com.dremio.exec.store.jdbc.dialect.arp.ArpDialect;
import com.dremio.exec.store.jdbc.dialect.arp.ArpYaml;
import com.google.common.annotations.VisibleForTesting;
import io.protostuff.Tag;
import java.util.Properties;
/**
 * Configuration for IBMSQL.
 */
@SourceType(value = "IBMSQL", label = "IBMSQL")
public class IBMSQLConf extends AbstractArpConf<IBMSQLConf> {
    private static final String ARP_FILENAME = "arp/implementation/IBMSQL-arp.yaml";
    private static final ArpDialect ARP_DIALECT =
            AbstractArpConf.loadArpFile(ARP_FILENAME, (ArpDialect::new));
    private static final String DRIVER = "com.ibm.cloud.sql.jdbc.Driver";
    /*
       https://cloud.ibm.com/docs/sql-query?topic=sql-query-jdbc
     */
    @Tag(1)
    @DisplayMetadata(label = "JDBC URL (Ex: jdbc:ibmcloudsql:{instance-crn}[?{key1}={value1}&{key2}={value2}...]")
    public String jdbcURL;


    @Tag(2)
    @Secret
    @DisplayMetadata(label = "Password")
    public String password;


    @Tag(3)
    @NotMetadataImpacting
    @DisplayMetadata(label = "Grant External Query access (External Query allows creation of VDS from a Snowflake query. Learn more here: https://docs.dremio.com/data-sources/external-queries.html#enabling-external-queries)")
    public boolean enableExternalQuery = false;


    @Tag(4)
    @DisplayMetadata(label = "Record fetch size")
    @NotMetadataImpacting
    public int fetchSize = 2000;
    @VisibleForTesting
    public String toJdbcConnectionString() {
        checkNotNull(this.jdbcURL, "JDBC URL is required");
        return jdbcURL;
    }


    @Tag(5)
    @DisplayMetadata(label = "Encrypt connection")
    public boolean useSsl = false;

    public IBMSQLConf(){}


    @Override
    @VisibleForTesting
    public JdbcPluginConfig buildPluginConfig(
            JdbcPluginConfig.Builder configBuilder,
            CredentialsService credentialsService,
            OptionManager optionManager
    ){
        return configBuilder.withDialect(getDialect())
                .withFetchSize(fetchSize)
                .withDatasourceFactory(this::newDataSource)
                .withAllowExternalQuery(enableExternalQuery)
                .build();
    }

    
    private CloseableDataSource newDataSource() {
    final Properties properties = new Properties();

        if (useSsl) {
        properties.setProperty("SSL", "1");
        }

        return DataSources.newGenericConnectionPoolDataSource(DRIVER,
                toJdbcConnectionString(), null, password, properties,
                DataSources.CommitMode.DRIVER_SPECIFIED_COMMIT_MODE);
    }
    
    @Override
    public ArpDialect getDialect() {
        return ARP_DIALECT;
    }
    @VisibleForTesting
    public static ArpDialect getDialectSingleton() {
        return ARP_DIALECT;
    }
}
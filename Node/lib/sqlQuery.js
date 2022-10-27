/* ------------------------------------------------------------------------------
/ Copyright IBM Corp. 2018
/
/ Licensed under the Apache License, Version 2.0 (the "License");
/ you may not use this file except in compliance with the License.
/ You may obtain a copy of the License at
/
/    http://www.apache.org/licenses/LICENSE-2.0
/
/ Unless required by applicable law or agreed to in writing, software
/ distributed under the License is distributed on an "AS IS" BASIS,
/ WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
/ See the License for the specific language governing permissions and
/ limitations under the License.
/ ------------------------------------------------------------------------------ */
"use strict";

const IBM = require("ibm-cos-sdk");
const fetch = require("node-fetch");
const xml2js = require("xml2js").parseString;
const csv = require('csvtojson');

function SQLQuery(apikey, instanceCRN, targetCOS) {
    this.apiKey = apikey;
    this.instanceCRN = instanceCRN;
    this.targetCOS = targetCOS;
    this.endpointAliasMapping = {
            "us-geo": "s3.us.cloud-object-storage.appdomain.cloud",
            "us": "s3.us.cloud-object-storage.appdomain.cloud",
            "dal-us-geo": "s3.dal.us.cloud-object-storage.appdomain.cloud",
            "dal": "s3.dal.us.cloud-object-storage.appdomain.cloud",
            "wdc-us-geo": "s3.wdc.us.cloud-object-storage.appdomain.cloud",
            "wdc": "s3.wdc.us.cloud-object-storage.appdomain.cloud",
            "sjc-us-geo": "s3.sjc.us.cloud-object-storage.appdomain.cloud",
            "sjc": "s3.sjc.us.cloud-object-storage.appdomain.cloud",
            "eu-geo": "s3.eu.cloud-object-storage.appdomain.cloud",
            "eu": "s3.eu.cloud-object-storage.appdomain.cloud",
            "ams-eu-geo": "s3.ams.eu.cloud-object-storage.appdomain.cloud",
            "ams": "s3.ams.eu.cloud-object-storage.appdomain.cloud",
            "fra-eu-geo": "s3.fra.eu.cloud-object-storage.appdomain.cloud",
            "fra": "s3.fra.eu.cloud-object-storage.appdomain.cloud",
            "mil-eu-geo": "s3.mil.eu.cloud-object-storage.appdomain.cloud",
            "mil": "s3.mil.eu.cloud-object-storage.appdomain.cloud",
            "us-south": "s3.us-south.cloud-object-storage.appdomain.cloud",
            "us-east": "s3.us-east.cloud-object-storage.appdomain.cloud",
            "jp-tok": "s3.jp-tok.cloud-object-storage.appdomain.cloud",
            "ap-geo": "s3.ap.cloud-object-storage.appdomain.cloud",
            "ap": "s3.ap.cloud-object-storage.appdomain.cloud",
            "tok-ap-geo": "s3.tok.ap.cloud-object-storage.appdomain.cloud",
            "tok": "s3.tok.ap.cloud-object-storage.appdomain.cloud",
            "seo-ap-geo": "s3.seo.ap.cloud-object-storage.appdomain.cloud",
            "seo": "s3.seo.ap.cloud-object-storage.appdomain.cloud",
            "hkg-ap-geo": "s3.hkg.ap.cloud-object-storage.appdomain.cloud",
            "hkg": "s3.hkg.ap.cloud-object-storage.appdomain.cloud",
            "eu-de": "s3.eu-de.cloud-object-storage.appdomain.cloud",
            "eu-gb": "s3.eu-gb.cloud-object-storage.appdomain.cloud",
            "ams03": "s3.ams03.cloud-object-storage.appdomain.cloud",
            "che01": "s3.che01.cloud-object-storage.appdomain.cloud",
            "hkg02": "s3.hkg02.cloud-object-storage.appdomain.cloud",
            "mel01": "s3.mel01.cloud-object-storage.appdomain.cloud",
            "mex01": "s3.mex01.cloud-object-storage.appdomain.cloud",
            "mil01": "s3.mil01.cloud-object-storage.appdomain.cloud",
            "tor01": "s3.tor01.cloud-object-storage.appdomain.cloud",
            "mon01": "s3.mon01.cloud-object-storage.appdomain.cloud",
            "osl01": "s3.osl01.cloud-object-storage.appdomain.cloud",
            "par01": "s3.par01.cloud-object-storage.appdomain.cloud",
            "sao01": "s3.sao01.cloud-object-storage.appdomain.cloud",
            "seo01": "s3.seo01.cloud-object-storage.appdomain.cloud",
            "sjc04": "s3.sjc04.cloud-object-storage.appdomain.cloud",
            "sng01": "s3.sng01.cloud-object-storage.appdomain.cloud",
            "au-syd": "s3.au-syd.cloud-object-storage.appdomain.cloud",
            "us-west": "s3.us-west.cloud-object-storage.test.appdomain.cloud"
    };

    let cosSplit = targetCOS.split('/');
    this.region = _mapEndpointCheck(this,targetCOS);
    this.bucketName = cosSplit[3];
    this.prefix = _prefixCheck(cosSplit[4]);

    this.xmlContentHeaders = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    };

    this.requestHeaders = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    };

    this.loggedOn = false;
}

SQLQuery.prototype.logon = function () {

    let response = fetch("https://iam.bluemix.net/identity/token", {
        "method": "POST",
        "headers": this.xmlContentHeaders,
        "body": `apikey=${this.apiKey}&grant_type=urn%3Aibm%3Aparams%3Aoauth%3Agrant-type%3Aapikey`
    });

    return response.then(res => {
        if (res.status === 200) {
            return res.json();
        } else {
            return `Authentication failed with HTTP code ${res.status}`;
        }
    }).then(json => {
        this.requestHeaders.Authorization = `Bearer ${json.access_token}`;
        this.loggedOn = true;
    });
};

SQLQuery.prototype.getJobs = function () {

    if (!this.loggedOn) {
        return "You are not logged into IBM Cloud";
    }

    let response = fetch(`https://api.dataengine.cloud.ibm.com/v3/sql_jobs?type=batch&instance_crn=${this.instanceCRN}`, {
        "method": "GET",
        "headers": this.requestHeaders
    });

    return response.then(res => {
        return res.json();
    }).then(jobs => {
        return jobs;
    });
};

SQLQuery.prototype.getJob = function (jobId) {
    if (!this.loggedOn) {
        return "You are not logged into IBM Cloud"
    }

    let response = fetch(`https://api.dataengine.cloud.ibm.com/v3/sql_jobs/${jobId}?instance_crn=${this.instanceCRN}`, {
        "method": "GET",
        "headers": this.requestHeaders
    });

    return response.then(res => {
        if (res.status === 200 || res.status === 201) {
            return res.json();
        } else {
            throw new Error(`SQL jobId ${jobId} unknown.`);
        }
    }).then(job => {
        return job;
    });
};

SQLQuery.prototype.submitSql = function (query) {

    if (!this.loggedOn) {
        return "You are not logged into IBM Cloud";
    }

    let sqlData = JSON.stringify({"statement": query, "resultset_target": this.targetCOS});

    let response = fetch(`https://api.dataengine.cloud.ibm.com/v3/sql_jobs?instance_crn=${this.instanceCRN}`, {
        "method": "POST",
        "headers": this.requestHeaders,
        "body": sqlData
    });

    return response.then(res => {
        if (res.status === 200 || res.status === 201) {
            return res.json();
        } else {
            throw new Error(`Failed. Received status ${res.status}`);
        }
    }).then(job => {
        return job;
    });
};

SQLQuery.prototype.waitForJob = function (jobId) {

    if (!this.loggedOn) {
        console.log("You are not logged into IBM Cloud");
    }

    return new Promise((resolve, reject) => {

        let checkStatus = setInterval(() => {

            let response = fetch(`https://api.dataengine.cloud.ibm.com/v3/sql_jobs/${jobId}?instance_crn=${this.instanceCRN}`, {
                "method": "GET",
                "headers": this.requestHeaders
            });

            return response.then(res => {

                if (res.status >= 400) {
                    throw new Error(`Job status check failed with HTTP code ${res.status}`);
                } else {
                    return res.json();
                }

            }).then(job => {

                let jobStatus = job.status;

                if (jobStatus === "completed") {
                    resolve(job.job_id);
                    clearInterval(checkStatus);

                } else if (jobStatus === "failed") {
                    reject(`Job ${jobId} has failed.`);
                    clearInterval(checkStatus);
                }
            });
        }, 2000);
    });
};

SQLQuery.prototype.getResult = function (jobId, maxResults = 0) {

    if (maxResults > 0) {
        
        return;

    }
    

    if (!this.loggedOn) {
        return "You are not logged into IBM Cloud";
    }

    let getBucketObject = () => {
        const self = this;
        return new Promise((resolve, reject) => {
            
            this.getJob(jobId).then(res => {
    
                if (res.status === "failed") {
                    return `SQL job with jobId ${jobId} did not finish successfully. No result available.`;
                } else if (res.status === "running") {
                    return `SQL job with jobId ${jobId} still running. Come back later.`;
                }
    
                const resultLocation = `https://${self.region}/${self.bucketName}?prefix=${self.prefix}jobid=${jobId}/part`;
    
                const response = fetch(resultLocation, {
                    "method": "GET",
                    "headers": self.requestHeaders
                });
    
                return response.then(res => {
                    if (res.status >= 400) {
                        throw new Error(res);
                    } else {
                        return res.text(); 
                    }
                }).then(res => {
                    xml2js(res, (err, result) => {
                        if (err) {
                            reject(err);
                        }
                        resolve(result);
                    });
                });
            });
        }).catch((err) =>{ 
            return err;
        });
    };

    const getJSONResult = (res) => {
        return new Promise((resolve, reject) => {

            let cosClient = new IBM.S3({
                "endpoint": "https://" + this.region,
                "apiKeyId": this.apiKey,
                "ibmAuthEndpoint": "https://iam.ng.bluemix.net/oidc/token"
            });

            let objectParams = {
                "Bucket": res.ListBucketResult.Name[0],
                "Key": res.ListBucketResult.Contents[0].Key[0]
            };

            return cosClient.getObject(objectParams, (err, data) => {

                if (err) {
                    reject(err);
                }
                let body = data.Body.toString('utf-8');

                let responseData = [];

                csv().fromString(body)
                    .on("json", (result) => {
                        responseData.push(result);
                    })
                    .on('done', (err) => {
                        if (err) {
                            reject(err);
                        }
                        resolve(responseData);
                    });
            });
        }).catch((err) =>{ 
            return err;
        });
    };

    return getBucketObject().then(res => getJSONResult(res));
};

SQLQuery.prototype.deleteResult = function (jobId) {

    if (!this.loggedOn) {
        return "You are not logged into IBM Cloud";
    }

    let self = this;

    let getJobObjects = (jobId) => {
        return new Promise((resolve, reject) => {
            self.getJob(jobId).then(res => {
                if (res.status === "failed") {    
                    throw new Error(`SQL job with jobId ${jobId} did not finish successfully. No result available.`);
                } else if (res.status === "running") {
                    throw new Error(`SQL job with jobId ${jobId} still running. Come back later.`);
                }
    
                const resultLocation = res.resultset_location.split('/');
                const hostBucket = resultLocation.slice(2, 4).join('/');
                const fileName = resultLocation.slice(4, resultLocation.length).join('/');
    
                const fileLocation = `https://${hostBucket}?prefix=${fileName}`;
    
                const response = fetch(fileLocation, {
                    "method": "GET",
                    "headers": self.requestHeaders
                });

                return response.then(res => {
                    if (res.status === 200 || res.status === 201) {
                        return res.text();
                    } else {
                        throw new Error(`Result object listing for job ${jobId} at ${res.resultset_location} failed with http code ${res.status}`);
                    }
                }).then(xml => {
                    xml2js(xml, (err, result) => {

                        if (err) {
                            throw new Error(err);
                        }
                        if (result.ListBucketResult.Contents) {
                            resolve(result.ListBucketResult);
                        } else {
                            reject(`There are no result objects for the jobId ${jobId}`);
                        }

                    });
                });
            });
        }).catch((err) =>{ 
            return err;
        });
    };

    let deleteBucketObjects = (bucketContents) => {
        return new Promise((resolve, reject) => {
            let cosClient = new IBM.S3({
                "endpoint": "https://" + this.region,
                "apiKeyId": this.apiKey,
                "ibmAuthEndpoint": "https://iam.ng.bluemix.net/oidc/token"
            });

            let bucketName = bucketContents.Name[0];
            let bucketObjects = {
                "Bucket": bucketName,
                "Delete": {
                    "Objects": []
                }
            };

            bucketContents.Contents.forEach(file => {
                bucketObjects.Delete.Objects.push({"Key": file.Key[0]});
            });

            return cosClient.deleteObjects(bucketObjects, (err, data) => {
                if (err) {
                    reject(err);
                } else {
                    resolve(data.Deleted);
                }
            });
        }).catch((err) =>{ 
            return err;
        });
    };

    return getJobObjects(jobId).then(res => deleteBucketObjects(res));

};

SQLQuery.prototype.runSql = function (query) {

   return new Promise((resolve, reject) => {
        this.logon().then(() => this.submitSql(query).then(res => {
                if (res) {
                    return res.job_id;
                } else {
                   reject(`Query failed`);
                   return;
                }
            }).then(id => {
                this.waitForJob(id).then((id) => {
                    if (id) {
                        return id;
                    } else {
                        reject(`Job ${id} has failed`);
                        return;
                    }
                }).then(id => {
                this.getResult(id).then((result) => {
                    resolve(result);
                    });
                });
            })
        )
    }).catch((err) => {
        return err;
    });
};

SQLQuery.prototype.sqlUILink = function () {
    if (!this.loggedOn) {
        return "You are not logged into IBM Cloud";
    }

    return `https://sql.ng.bluemix.net/sqlquery/?instance_crn=${this.instanceCRN}`;
};

//// helper functions

function _prefixCheck(prefix) {
    if (prefix) {
        return prefix + '/';
    } else {
        return prefix;
    }
}

function _mapEndpointCheck(self, url) {
    
    let urlEndpoint = url.split('/')[2];
    
    function regionCheck(endpoint) {
        for (let key in self.endpointAliasMapping) {
            if (self.endpointAliasMapping[key] === endpoint) {
                return true;
            } 
        }
    }

    if (self.endpointAliasMapping.hasOwnProperty(urlEndpoint)) {
        urlEndpoint = self.endpointAliasMapping[urlEndpoint];
    } else if (regionCheck(urlEndpoint)) {
        urlEndpoint = urlEndpoint;
    }
    else {
        return new Error(`${urlEndpoint} is not a valid COS region.`);
    }
    return urlEndpoint;
       
}

module.exports = SQLQuery;

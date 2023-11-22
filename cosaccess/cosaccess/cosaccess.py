# ------------------------------------------------------------------------------
# Copyright IBM Corp. 2023
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_platform_services import IamPolicyManagementV1
from ibm_platform_services import IamIdentityV1
from ibm_platform_services import UserManagementV1
from ibm_platform_services import IamAccessGroupsV2
from ibm_platform_services.iam_access_groups_v2 import AccessGroupMembersPager
from ibm_platform_services.iam_identity_v1 import ApiKeyInsideCreateServiceIdRequest
from ibm_platform_services import ApiException
from ibm_cos_sdk_config.resource_configuration_v1 import ResourceConfigurationV1
import ibm_boto3
from ibm_botocore.client import Config
from xml.etree import ElementTree
import requests
import re
import pandas as pd

class CosAccessManager:

    def __init__(self, apikey: str, account_id=None):
        self._apikey = apikey
        self._authenticator = IAMAuthenticator(self._apikey)  # So we only authenticate once for all platform SDK libs
        self._policy_service = IamPolicyManagementV1(authenticator=self._authenticator)
        self._identity_service = IamIdentityV1(authenticator=self._authenticator)
        if not account_id:  # We default to the account of the provided API Key
            self._account_id = self._identity_service.get_api_keys_details(iam_api_key=self._apikey).get_result()[
                "account_id"]
        else:
            self._account_id = account_id
        self._user_management_service = UserManagementV1(
            authenticator=self._authenticator)  # To resolve clear text user names
        self._access_groups_service = IamAccessGroupsV2(
            authenticator=self._authenticator)  # To resolve clear access group names
        self._cos_resource_config_service = ResourceConfigurationV1(
            authenticator=self._authenticator)  # To retrieve COS instance IDs for provided COS bucket names
        pd.set_option('display.max_colwidth', None)
        self._platform_roles = ["Viewer", "Editor", "Operator", "Administrator"]
        self._bucket_roles = ["Manager", "Reader", "Writer"]
        self._object_roles = ["ObjectWriter", "ObjectReader", "ContentReader", "NotificationsManager"]


    def _parse_role(self, role_crn: str):
        if "crn:v1:bluemix:public:iam::::role:" in role_crn:  # Platform role
            return role_crn[34:]
        elif "crn:v1:bluemix:public:iam::::serviceRole:" in role_crn:  # Bucket role
            return role_crn[41:]  # Service role
        elif "crn:v1:bluemix:public:cloud-object-storage::::serviceRole:" in role_crn:  # Object role
            return role_crn[58:]  # Service role
        return role_crn # Whatever

    def _expand_role(self, role: str):
        if role in self._platform_roles:
            return "crn:v1:bluemix:public:iam::::role:" + role
        elif role in self._bucket_roles:
            return "crn:v1:bluemix:public:iam::::serviceRole:" + role
        elif role in self._object_roles:
            return "crn:v1:bluemix:public:cloud-object-storage::::serviceRole:" + role
        else:
            return role
    def _validate_roles(self, roles: list[str]):
        for role in roles:
            if role not in self._platform_roles and role not in self._bucket_roles and role not in self._object_roles:
                raise ValueError("Supported roles are " + str(self._platform_roles) + ", "
                                 + str(self._bucket_roles) + " and " + str(self._object_roles))

    def list_policies(self, roles: list[str] = None):
        """Returns all policies in the account as JSON, optionally filtered by roles of the policies

        Parameters:
        roles (list[str]): Optional: At least one of these roles in this list must be used by the policy

       Returns:
        int:JSON dict with all policies of the account
        """

        policies = []
        for policy in self._policy_service.list_v2_policies(account_id=self._account_id).get_result()["policies"]:
            role_match = False
            for role in policy["control"]["grant"]["roles"]:
                if roles and self._parse_role(role["role_id"]) in roles:
                    role_match = True
            if role_match or not roles:
                policies.append(policy)
        return policies

    def get_policy(self, policy_id: str):
        policy_response = self._policy_service.get_v2_policy(id=policy_id)
        policy = policy_response.get_result()
        policy["Etag"]=policy_response.get_headers().get("Etag")
        return policy

    def list_policies_for_service(self, serviceName: str, roles: list[str] = None):
        """Returns all policies on the provided service type and optionally roles.

        Parameters:
        serviceName (str): Name of a service type, for instance "cloud-object-storage"
        roles (list[str]): Optional: At least one of these roles in this list must be used by the policy

        Returns:
        int:JSON dict with all policies for the provided service type in the account
        """

        policies = []
        for policy in self.list_policies(roles=roles):
            attributes = 0  # The service can appear in multiple attributes in the policy
            for policy_attribute in policy["resource"]["attributes"]:
                if policy_attribute["key"] == "serviceName":
                    if policy_attribute["value"] == serviceName:
                        attributes += 1
                        break
            if attributes > 0:
                policies.append(policy)
        return policies

    def list_policies_for_cos_instance(self, cosServiceInstance: str, roles: list[str] = None):
        """Returns all policies on the provided COS instance and optionally roles

        Parameters:
        cosServiceInstance (str): COS instance ID
        roles (list[str]): Optional: At least one of these roles in this list must be used by the policy

        Returns:
        int:JSON dict with all policies for the provided COS instance
        """

        policies = []
        for policy in self.list_policies_for_service("cloud-object-storage", roles=roles):
            attributes = 0  # The service instance can appear in multiple attributes in the policy
            for policy_attribute in policy["resource"]["attributes"]:
                if policy_attribute["key"] == "serviceInstance":
                    if policy_attribute["value"] == cosServiceInstance:
                        attributes += 1
                        break
            if attributes > 0:
                policies.append(policy)
        return policies

    def list_policies_for_cos_bucket(self, cosBucket: str = None, prefix: str = None, roles: list[str] = None):
        """Returns all policies on the provided COS bucket and path (optional) and roles (optional)

        Parameters:
        cosBucket (str): COS bucket name. Optional: when not provided all policies to COS services are returned
        prefix (str): Optional: Prefix path in the bucket
        roles (list[str]): Optional: At least one of these roles in this list must be used by the policy

        Returns:
        int:JSON dict with all policies for the provided COS bucket and prefix
        """

        bucket_policies = []
        all_cos_policies = self.list_policies_for_service("cloud-object-storage", roles=roles)
        if not cosBucket:
            return all_cos_policies
        # Filter for policies that apply to the provided bucket
        for policy in all_cos_policies:
            attributes = 0  # The COS bucket can appear in multiple attributes in the policy
            bucket_policy = False
            for policy_attribute in policy["resource"]["attributes"]:
                if policy_attribute["key"] == "resourceType" and policy_attribute["value"] == "bucket":
                    bucket_policy = True
                if policy_attribute["key"] == "resource" and policy_attribute["value"] == cosBucket:
                    attributes += 1
            # The policy applies if it is not scoped on bucket at all or if it is scoped on bucket
            # and the bucket name is the provided one (attributes > 0):
            if (attributes > 0 and bucket_policy) or (not bucket_policy):
                bucket_policies.append(policy)
        if not prefix:
            return bucket_policies
        # We need to filter the bucket policies further of a specific prefix was provided
        policies = []
        for bucket_policy in bucket_policies:
            if "rule" in bucket_policy:
                for condition in bucket_policy["rule"]["conditions"]:
                    if "key" in condition:
                        if condition["key"] == "{{resource.attributes.path}}":
                            # Multiple path conditions are returned as array, otherwise single string
                            if isinstance(condition["value"], str):
                                conditions = [condition["value"]]
                            else:
                                conditions = condition["value"]
                            for condition in conditions:
                                # For Python regex we need to escape literal dots in the condition string and
                                # then replace asterisk with dot + asterisk (zero or more of any character)
                                condition_expression = re.compile(condition.replace(".", "\\.").replace("*", ".")+"*")
                                if condition_expression.match(prefix):
                                    policies.append(bucket_policy)
                                    break
            else:
                policies.append(bucket_policy)  # Bucket policies without rule conditions always apply to the prefix
        return policies

    def grant_bucket_access(self, roles: list[str],
                            cos_bucket: str, prefixes: list[str] = None,
                            access_group_name: str = None, access_group_id: str = None,
                            user_id: str = None, user_name: str = None,
                            service_id: str = None, service_id_name=None):
        return self._write_bucket_policy(policy_id=None, roles=roles, cos_bucket=cos_bucket,
                                         prefixes=prefixes,
                                         access_group_name=access_group_name, access_group_id=access_group_id,
                                         user_id=user_id, user_name=user_name,
                                         service_id=service_id, service_id_name=service_id_name)
    def update_bucket_access(self, policy_id: None,
                             roles: list[str],
                             cos_bucket: str, prefixes: list[str] = None,
                             access_group_name: str = None, access_group_id:str = None,
                             user_id:str = None, user_name:str = None,
                             service_id:str = None, service_id_name = None):
        return self._write_bucket_policy(policy_id=policy_id, roles=roles,
                                         cos_bucket=cos_bucket, prefixes=prefixes,
                                         access_group_name=access_group_name, access_group_id=access_group_id,
                                         user_id=user_id, user_name=user_name,
                                         service_id=service_id, service_id_name=service_id_name)

    def _write_bucket_policy(self, policy_id: None,
                             roles: list[str],
                             cos_bucket: str, prefixes: list[str] = None,
                             access_group_name: str = None, access_group_id:str = None,
                             user_id:str = None, user_name:str = None,
                             service_id:str = None, service_id_name = None):
        if [bool(user_name), bool(user_id),
            bool(service_id_name), bool(service_id),
            bool(access_group_name), bool(access_group_id)].count(True) != 1:
            raise ValueError("You must provide exactly one of the parameters user_name, user_id, service_id_name \
                              service_id, access_group_name or access_group_id.")
        cos_instance = self.get_cos_instance_id(cos_bucket)
        access_group = None
        iam_id = None
        if access_group_id:
            access_group = access_group_id
        elif access_group_name:
            access_group = self.get_access_group_id(access_group_name)
        elif user_id:
            iam_id = user_id
        elif user_name:
            iam_id = self.get_user_iam_id(user_name)
        elif service_id:
            iam_id = service_id
        else:
            iam_id = self.get_service_id_iam_id(service_id_name)
        self._validate_roles(roles)
        control = {"grant": {"roles": []}}
        for role in roles:
            control["grant"]["roles"].append({"role_id": self._expand_role(role)})
        resource = {"attributes": [{"value": cos_instance, "operator": "stringEquals", "key": "serviceInstance"},
                                   {"value": "cloud-object-storage", "operator": "stringEquals", "key": "serviceName"},
                                   {"value": self._account_id, "operator": "stringEquals", "key": "accountId"},
                                   {"value": "bucket", "operator": "stringEquals", "key": "resourceType"},
                                   {"value": cos_bucket, "operator": "stringEquals", "key": "resource"}
                                   ]}
        subject = {"attributes": []}
        if access_group:
            subject["attributes"].append({"value": access_group, "operator": "stringEquals", "key": "access_group_id"})
        if iam_id:
            subject["attributes"].append({"value": iam_id, "operator": "stringEquals", "key": "iam_id"})

        pattern = "attribute-based-condition:resource:literal-and-wildcard"
        if prefixes:
            rule = {"operator": "or", "conditions": []}
            for idx, prefix in enumerate(prefixes):
                if prefix[-1] != "*": prefixes[idx] = prefix + "*"
            if len(prefixes) == 1:
                prefix_value = prefixes[0]
                prefixMatchOperator = "stringMatch"
            else:
                prefix_value = prefixes
                prefixMatchOperator = "stringMatchAnyOf"
            rule["conditions"].append({
                "operator": "and",
                "conditions": [{
                    "key": "{{resource.attributes.prefix}}",
                    "operator": prefixMatchOperator,
                    "value": prefix_value
                }, {
                    "key": "{{resource.attributes.delimiter}}",
                    "operator": "stringEqualsAnyOf",
                    "value": ["/", ""]
                }]
            })
            rule["conditions"].append({
                "key": "{{resource.attributes.path}}",
                "operator": prefixMatchOperator,
                "value": prefix_value
            })
        else:
            rule = None
        if policy_id:
            etag = self.get_policy(policy_id)["Etag"]
            result = self._policy_service.replace_v2_policy(id=policy_id, if_match=etag,
                                                            type="access", control=control,
                                                            subject=subject, resource=resource, rule=rule,
                                                            pattern=pattern).get_result()
        else:
            result = self._policy_service.create_v2_policy(type="access", control=control,
                                                           subject=subject, resource=resource, rule=rule,
                                                           pattern=pattern).get_result()
        return result["id"]

    def remove_bucket_access(self, policy_id: str):
        self._policy_service.delete_v2_policy(policy_id)

    def get_users(self):
        """Returns the users in the account

        Returns:
        Pandas dataframe with all user profiles in the account
        """
        page = self._user_management_service.list_users(self._account_id, limit=100).get_result()
        users = pd.DataFrame(page["resources"])
        while "next_url" in page:
            next_url = page["next_url"]
            start = next_url[next_url.index("_start=") + 7:]
            start = start[:start.index("&")]
            page = self._user_management_service.list_users(self._account_id, limit=100, start=start).get_result()
            users = pd.concat([users, pd.DataFrame(page["resources"])], ignore_index=True)
        return users

    def get_user_iam_id(self, user_id: str):
        for idx, user in self.get_users().iterrows():
            if user["user_id"] == user_id:
                return user["iam_id"]
        raise ValueError(
            "User " + user_id + " is not in the account " + self._account_id + ". Use list_users() for users in the account.")

    def get_user_name(self, iam_id: str):
        """Returns the user name of a IAM user ID

        Parameters:
        iam_id (str): IAM User ID

        Returns:
        str:Clear text user name in format <Given Name> <Last Name> <email>
        """
        user_profile = self._user_management_service.get_user_profile(account_id=self._account_id,
                                                                      iam_id=iam_id).get_result()
        return user_profile["firstname"] + " " + user_profile["lastname"] + " " + user_profile["user_id"]

    def get_service_ids(self):
        """Returns the Service IDs in the account

        Returns:
        Pandas dataframe with all Servie IDs in the account
        """
        page = self._identity_service.list_service_ids(account_id=self._account_id, pagesize=100).get_result()
        service_ids = page["serviceids"]
        while "next" in page:
            href = page["next"]
            pagetoken = href[href.index("pagetoken=") + 10:]
            page = self._identity_service.list_service_ids(account_id=self._account_id, pagetoken=pagetoken,
                                                           pagesize=100).get_result()
            service_ids.append(page["serviceids"])
        return pd.DataFrame(service_ids)

    def get_service_id_iam_id(self, service_id: str):
        for idx, service_id_profile in self.get_service_ids().iterrows():
            if str(service_id_profile["name"]) == service_id:
                return service_id_profile["iam_id"]
        raise ValueError(
            "Service ID " + service_id + " is not in the account " + self._account_id + ". Use get_service_ids() for Service IDs in the account.")

    def get_service_id_name(self, iam_id: str):
        """Returns the Service ID display name service ID

        Parameters:
        service_id (str): Service ID

        Returns:
        str:Clear text display name for Service ID
        """
        return self._identity_service.get_service_id(id=iam_id[4:]).get_result()["name"]

    def create_service_id(self, service_id_name, with_apikey = False):
        apikeyrequest = None
        if with_apikey:
            apikeyrequest = ApiKeyInsideCreateServiceIdRequest(name=service_id_name+"_apikey", store_value=True)
        return self._identity_service.create_service_id(account_id=self._account_id,
                                                        name=service_id_name,
                                                        apikey=apikeyrequest).get_result()

    def delete_service_id(self, service_id_name:str = None, service_id:str = None):
        if [bool(service_id_name), bool(service_id)].count(True) != 1:
            raise ValueError("You must provide exactly one of the parameters service_id_name or service_id.")
        if service_id:
            id = service_id
        else:
            id = self.get_service_id_iam_id(service_id_name)[4:]
        self._identity_service.delete_service_id(id)

    def get_service_id_details(self, service_id:str = None, service_id_name:str = None):
        if [bool(service_id_name), bool(service_id)].count(True) != 1:
            raise ValueError("You must provide exactly one of the parameters service_id_name or service_id.")
        if service_id:
            id = service_id
        else:
            id = self.get_service_id_iam_id(service_id_name)[4:]
        response = self._identity_service.get_service_id(id)
        service_id_details = response.get_result()
        service_id_details["Etag"]=response.get_headers().get("Etag")
        return service_id_details

    def get_access_groups(self):
        """Returns the access groups in the account

        Returns:
        Pandas dataframe with all access groups in the account
        """
        page = self._access_groups_service.list_access_groups(account_id=self._account_id, limit=100).get_result()
        access_groups = pd.DataFrame(page["groups"])
        total_count = page["total_count"] - 1
        offset = 0
        while offset < total_count:
            offset = page["offset"] + page["limit"]
            page = self._access_groups_service.list_access_groups(account_id=self._account_id, offset=offset,
                                                                  limit=100).get_result()
            access_groups = pd.concat([access_groups, pd.DataFrame(page["groups"])], ignore_index=True)
        return access_groups

    def get_access_group_id(self, access_group: str):
        for idx, access_group_profile in self.get_access_groups().iterrows():
            if str(access_group_profile["name"]) == access_group:
                return access_group_profile["id"]
        raise ValueError(
            "Access Group " + access_group + " is not in the account " + self._account_id + ". Use get_access_groups() for access groups in the account.")

    def get_access_group_name(self, access_group_id: str):
        """Returns the Access group display name service ID

        Parameters:
        access_group_id (str): Access Group ID

        Returns:
        str:Clear text display name for Access Group
        """
        return self._access_groups_service.get_access_group(access_group_id=access_group_id).get_result()["name"]

    def create_access_group(self, access_group_name):
        response = self._access_groups_service.create_access_group(account_id=self._account_id, name=access_group_name)
        return response.get_result()["id"]

    def delete_access_group(self, access_group_name:str = None, access_group_id:str = None, force:bool = False):
        if [bool(access_group_name), bool(access_group_id)].count(True) != 1:
            raise ValueError("You must provide exactly one of the parameters access_group_name or access_group_id.")
        if access_group_id:
            id = access_group_id
        else:
            id = self.get_access_group_id(access_group_name)
        self._access_groups_service.delete_access_group(access_group_id=id, force=force)

    def get_access_group_members(self, access_group_name:str = None, access_group_id:str = None):
        if [bool(access_group_name), bool(access_group_id)].count(True) != 1:
            raise ValueError("You must provide exactly one of the parameters access_group_name or access_group_id.")
        if access_group_id:
            id = access_group_id
        else:
            id = self.get_access_group_id(access_group_name)
        members = []
        pager = AccessGroupMembersPager(
            client=self._access_groups_service,
            access_group_id=id,
        )
        while pager.has_next():
            next_page = pager.get_next()
            assert next_page is not None
            members.extend(next_page)
        for member in members:
            if member["type"] == "service":
                member["service_id_name"] = self.get_service_id_name(member["iam_id"])
                member["user_name"] = ""
            else:
                member["user_name"] = self.get_user_name(member["iam_id"])
                member["service_id_name"] = ""
        return pd.DataFrame(members)

    def _parse_member_parms(self, access_group_name:str = None, access_group_id:str = None,
                            user_name:str = None, user_id:str = None,
                            service_id_name:str = None, service_id:str = None):
        if [bool(access_group_name), bool(access_group_id)].count(True) != 1:
            raise ValueError("You must provide exactly one of the parameters access_group_name or access_group_id.")
        if [bool(user_name), bool(user_id),
            bool(service_id_name), bool(service_id)].count(True) != 1:
            raise ValueError("You must provide exactly one of the parameters user_name, user_id, service_id_name or service_id.")
        if access_group_id:
            id = access_group_id
        else:
            id = self.get_access_group_id(access_group_name)
        if user_id:
            iam_id = user_id
            type = 'user'
        elif user_name:
            iam_id = self.get_user_iam_id(user_name)
            type = 'user'
        elif service_id:
            iam_id = service_id
            type = 'service'
        else:
            iam_id = self.get_service_id_iam_id(service_id_name)
            type = 'service'
        return {"id": id, "iam_id": iam_id, "type": type}

    def add_member_to_access_group(self, access_group_name:str = None, access_group_id:str = None,
                                         user_name:str = None, user_id:str = None,
                                         service_id_name:str = None, service_id:str = None):
        parms = self._parse_member_parms(access_group_name=access_group_name, access_group_id=access_group_id,
                                         user_name=user_name, user_id=user_id,
                                         service_id_name=service_id_name, service_id=service_id)
        member = IamAccessGroupsV2.AddGroupMembersRequestMembersItem(iam_id=parms["iam_id"], type=parms["type"])
        self._access_groups_service.add_members_to_access_group(access_group_id=parms["id"], members=[member])

    def delete_member_from_access_group(self, access_group_name:str = None, access_group_id:str = None,
                                        user_name:str = None, user_id:str = None,
                                        service_id_name:str = None, service_id:str = None):
        parms = self._parse_member_parms(access_group_name=access_group_name, access_group_id=access_group_id,
                                         user_name=user_name, user_id=user_id,
                                         service_id_name=service_id_name, service_id=service_id)
        self._access_groups_service.remove_member_from_access_group(access_group_id=parms["id"], iam_id=parms["iam_id"])

    def get_policies_for_cos_bucket(self, cosBucket: str = None, prefix: str = None, roles: list[str] = None):
        """Returns policies for provided COS bucket, path (optional) and roles (optional) as dataframe

        Parameters:
        cosBucket (str): COS bucket name
        prefix (str): Optional: Prefix path in the bucket
        roles (list[str]): Optional: Roles for COS access

        Returns:
        Pandas dataframe with bucket policies
        """
        data = []
        for i in self.list_policies_for_cos_bucket(cosBucket=cosBucket, prefix=prefix, roles=roles):
            policy = {"instance": "", "bucket": "", "paths": "", "roles": [], "user": "", "service_id": "",
                      "access_group": "", "access_group_id": "", "iam_id": "", "other_subject": ""}
            for j in i["resource"]["attributes"]:
                if j["key"] == "serviceInstance":
                    policy["instance"] = j["value"]
                if j["key"] == "resource":
                    policy["bucket"] = j["value"]
            policy["policy_id"] = i["id"]
            roles = []
            for j in i["control"]["grant"]["roles"]:
                roles.append(self._parse_role(j["role_id"]))
            policy["roles"] = roles
            for j in i["subject"]["attributes"]:
                if j["key"] == "iam_id" and j["value"].startswith("IBMid-"):
                    policy["iam_id"] = j["value"]
                    try:
                        policy["user"] = self.get_user_name(j["value"])
                    except ApiException as e:
                        pass
                elif j["key"] == "iam_id" and j["value"].startswith("iam-ServiceId-"):
                    policy["iam_id"] = j["value"]
                    policy["service_id"] = self.get_service_id_name(j["value"])
                elif j["key"] == "access_group_id":
                    policy["access_group_id"] = j["value"]
                    policy["access_group"] = self.get_access_group_name(j["value"])
                else:
                    policy["other_subject"] = j["key"] + "=" + j["value"]
            if "rule" in i:
                for condition in i["rule"]["conditions"]:
                    if "key" in condition:
                        if condition["key"] == "{{resource.attributes.path}}":
                            policy["paths"] = condition["value"]
            data.append(policy)
        return pd.DataFrame(data)

    def get_cos_instance_id(self, cosBucket:str):
        return self._cos_resource_config_service.get_bucket_config(cosBucket).get_result()["service_instance_id"]

    def get_cos_instance_crn(self, cosBucket:str):
        return self._cos_resource_config_service.get_bucket_config(cosBucket).get_result()["service_instance_crn"]

    def list_cos_endpoints(self):
        response = requests.get("https://control.cloud-object-storage.cloud.ibm.com/v2/endpoints").json()
        return response["service-endpoints"]

    def get_cos_endpoint(self, cos_bucket):
        response = requests.post(
            "https://iam.cloud.ibm.com/identity/token",
            headers = {"Content-Type": "application/x-www-form-urlencoded"},
            data="grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={}".format(self._apikey)
        )
        token = response.json()["access_token"]
        response = requests.get(
            "https://s3.us.cloud-object-storage.appdomain.cloud/?extended",
            headers={"Content-Type": "text/plain",
                     "authorization": "Bearer {}".format(token),
                     "ibm-service-instance-id": self.get_cos_instance_id(cos_bucket)}
        )
        xml_response = ElementTree.fromstring(response.content)
        cos_region = None
        for bucket in xml_response[5]:
            if bucket[0].text == cos_bucket:
                locationConstraint = bucket[2].text
                cos_region = locationConstraint[:locationConstraint.rfind("-")]
        if not cos_region:
            raise ValueError("Bucket {} could not be found.".format(cos_bucket))
        cos_endpoints = self.list_cos_endpoints()
        for i in cos_endpoints.keys():
            for j in cos_endpoints[i]:
                for k in cos_endpoints[i][j]["public"]:
                    if k == cos_region:
                        return "https://" + cos_endpoints[i][j]["public"][k]
        raise ValueError("Endpoint for region {} could not be found.".format(cos_region))

    def touch_cos_object(self, cos_bucket, object_path):
        cos_endpoint = self.get_cos_endpoint(cos_bucket)
        cosresource = ibm_boto3.resource("s3", ibm_api_key_id=self._apikey,
                                         ibm_service_instance_id=self.get_cos_instance_crn(cos_bucket),
                                         config=Config(signature_version="oauth"),
                                         endpoint_url=cos_endpoint)
        cosresource.Object(cos_bucket, object_path).put(Body="")

    def delete_cos_object(self, cos_bucket, object_path):
        cos_endpoint = self.get_cos_endpoint(cos_bucket)
        cosclient = ibm_boto3.client("s3", ibm_api_key_id=self._apikey,
                                     ibm_service_instance_id=self.get_cos_instance_crn(cos_bucket),
                                     config=Config(signature_version="oauth"),
                                     endpoint_url=cos_endpoint)
        cosclient.delete_object(Bucket=cos_bucket, Key=object_path)

    def get_cos_objects(self, cos_bucket):
        cos_endpoint = self.get_cos_endpoint(cos_bucket)
        objects = []
        cosresource = ibm_boto3.resource("s3", ibm_api_key_id=self._apikey,
                                         ibm_service_instance_id=self.get_cos_instance_crn(cos_bucket),
                                         config=Config(signature_version="oauth"),
                                         endpoint_url=cos_endpoint)
        for file in cosresource.Bucket(cos_bucket).objects.all():
            objects.append({"name": file.key, "last_modified": file.last_modified, "owner": file.owner, "size": file.size})
        return pd.DataFrame(objects)

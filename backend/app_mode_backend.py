from typing import List, Dict
import kubernetes as k8s
import k8s_api, k8s_config, cluster_mode_backend as cmb

# Note: call k8s_config.update_available_clusters() before use!

APP_CRD_GROUP = "app.k8s.io"
APP_CRD_PLURAL = "applications"
APP_CRD_VERSION = "v1beta1"

DPB_CRD_GROUP = "mcm.ibm.com"
DPB_CRD_PLURAL = "deployables"
DPB_CRD_VERSION = "v1alpha1"

def cluster_applications(cluster_name: str) -> List[Dict]:
	"""
	Returns all the applications that belong to the given cluster.

	:param (str) cluster_name
	:return: (List[Dict]) list of dicts, where each dict represents an Application
	"""

	# retrieve the cluster's Applications
	api_client = k8s_api.api_client(cluster_name, "CustomObjectsApi")
	try:
		apps = api_client.list_cluster_custom_object(
			group = APP_CRD_GROUP,
			version = APP_CRD_VERSION,
			plural = APP_CRD_PLURAL)["items"]
	except k8s.client.rest.ApiException:
		return []
	
	# insert cluster attribute into metadata
	for app in apps:
		app["metadata"]["cluster_name"] = cluster_name
	return apps

def all_applications() -> List[Dict]:
	"""
	Returns all applications across all clusters that can be accessed.

	:return: (List[Dict]) list of dicts, where each dict represents an Application
	"""

	cluster_names = k8s_config.all_cluster_names()
	applications = []
	for cluster_name in cluster_names:
		applications += cluster_applications(cluster_name)
	return applications

def cluster_deployables(cluster_name: str) -> List[Dict]:
	"""
	Returns a list of all the Deployables that belong to the given cluster.

	:param (str) cluster_name
	:return: (List[Dict]) list of dicts, where each dict represents a Deployable
	"""

	# retrieve the cluster's Deployables
	api_client = k8s_api.api_client(cluster_name, "CustomObjectsApi")
	try:
		results = api_client.list_cluster_custom_object(group = DPB_CRD_GROUP,
			version = DPB_CRD_VERSION,
			plural = DPB_CRD_PLURAL)["items"]
	except k8s.client.rest.ApiException as e:
		return []

	# add cluster name to metadata of Deployables
	for result in results:
		result["metadata"]["cluster_name"] = cluster_name
	return results

def application_deployable_names(cluster_name: str, namespace: str, app_name: str) -> List[str]:
	"""
	Returns the names of the Deployables that belong the specified Application.

	:param (str) cluster_name: name of cluster where the Application resides
	:param (str) namespace: namespace where the Application resides
	:param (str) app_name
	:return: (List[str]) list of Deployable names
	"""

	# find the Application using the given arguments
	api_client = k8s_api.api_client(cluster_name, "CustomObjectsApi")
	field_selector = "metadata.name=" + app_name
	results = api_client.list_namespaced_custom_object(namespace = namespace,
		group = APP_CRD_GROUP,
		version = APP_CRD_VERSION,
		plural = APP_CRD_PLURAL,
		field_selector = field_selector)["items"]

	# if we couldn't find the Application, return None
	if len(results) == 0:
		print("No application found with name", app_name, "in cluster", cluster_name, "and ns", namespace + ".")
		return

	# return the list of deployables specified in the Application's annotations
	app = results[0]
	dpb_list = app["metadata"]["annotations"]["apps.ibm.com/deployables"].split(",")
	return dpb_list

def application_deployables(cluster_name: str, namespace: str, app_name: str) -> List[Dict]:
	"""
	Returns the Deployables that belong to the specified Application.

	:param (str) cluster_name: name of cluster where the Application resides
	:param (str) namespace: namespace where the Application resides
	:param (str) app_name
	:return: (List[str]) list of dicts, where each dict represents a Deployable
	"""
	
	# find the names of the Deployables that belong to this Application
	dpb_names = application_deployable_names(cluster_name, namespace, app_name)
	if dpb_names == None:
		return []

	# aggregate Deployables across all clusters
	cluster_names = k8s_config.all_cluster_names()
	deployables = []
	for cluster_name in cluster_names:
		deployables += cluster_deployables(cluster_name)

	# filter down to this application's Deployables
	app_dpbs = [ dpb for dpb in deployables if dpb["metadata"]["name"] in dpb_names ]
	return app_dpbs

def deployable_resource(cluster_name: str, namespace: str, deployable_name: str) -> Dict:
	"""
	Returns info on the resource (deployer) deployed by the specified Deployable.

	:param (str) cluster_name: name of cluster where Deployable resides
	:param (str) namespace: namespace where Deployable resides
	:param (str) deployable_name
	:return: (Dict) dict with info about the deployer, or empty dict if deployer kind (e.g. helm) is not accessible
	"""
		
	# find the Deployable using the arguments given
	api_client = k8s_api.api_client(cluster_name, "CustomObjectsApi")
	field_selector = "metadata.name=" + deployable_name
	results = api_client.list_namespaced_custom_object(namespace = namespace,
		group = DPB_CRD_GROUP,
		version = DPB_CRD_VERSION,
		plural = DPB_CRD_PLURAL,
		field_selector = field_selector)["items"]

	# if we couldn't find the Deployable, return None
	if len(results) == 0:
		print("No Deployable found with name", deployable_name, "in cluster", cluster_name, "and ns", namespace + ".")
		return

	# extract the managed resource from the Deployable dict
	deployable = results[0]
	kind = deployable["spec"]["deployer"]["kind"]

	if kind != 'helm':
		deployer_name = deployable["spec"]["deployer"]["kube"]["template"]["metadata"]["name"]
		deployer_namespace = deployable["spec"]["deployer"]["kube"]["namespace"]
	else:
		pass

	deployer_dict = {}

	# go through given namespace in all clusters until we find a resource that has name = deployer_name
	cluster_names = k8s_config.all_cluster_names()
	for cluster_name in cluster_names:
		candidates = []
		if kind == 'Deployment':
			candidates = cmb.namespace_deployments(deployer_namespace, cluster_name)
		elif kind == 'Service':
			candidates = cmb.namespace_services(deployer_namespace, cluster_name)
		for res in candidates:
			if res.metadata.name == deployer_name:
				deployer_dict = res.to_dict()
				deployer_dict["metadata"]["cluster_name"] = cluster_name
				deployer_dict["kind"] = kind
				break

		# if already matched
		if deployer_dict != {}:
			break

	return deployer_dict

def deployable_resource_name(cluster_name: str, namespace: str, deployable_name: str) -> Dict:
	"""
	Returns name of resource (deployer) deployed by the specified Deployable.
	(Same logic as first part of deployable_resource() above)

	:param (str) cluster_name: name of cluster where Deployable resides
	:param (str) namespace: namespace where Deployable resides
	:param (str) deployable_name
	:return: (str) name of deployer, or empty string if deployer kind is helm
	"""

	# find the Deployable using the arguments given
	api_client = k8s_api.api_client(cluster_name, "CustomObjectsApi")
	field_selector = "metadata.name=" + deployable_name
	results = api_client.list_namespaced_custom_object(namespace=namespace,
		group=DPB_CRD_GROUP,
		version=DPB_CRD_VERSION,
		plural=DPB_CRD_PLURAL,
		field_selector=field_selector)["items"]

	# if we couldn't find the Deployable, return None
	if len(results) == 0:
		print("No Deployable found with name", deployable_name, "in cluster", cluster_name, "and ns", namespace + ".")
		return

	# extract the managed resource from the Deployable dict
	deployable = results[0]
	kind = deployable["spec"]["deployer"]["kind"]

	if kind != 'helm':
		deployer_name = deployable["spec"]["deployer"]["kube"]["template"]["metadata"]["name"]
		return deployer_name

	return ""

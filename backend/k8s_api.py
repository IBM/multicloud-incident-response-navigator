import kubernetes as k8s
from kubernetes import client, config
import k8s_config

def api_client(cluster_name: str, api_class: str) -> k8s.client.apis:
	"""
	Creates and returns a python k8s api client of the specified class and pointing to the specified cluster.

	Usage: 	Use this function whenever you want a python k8s api client.
			Python k8s api documentation: https://github.com/kubernetes-client/python/blob/master/kubernetes/README.md

	:param (str) cluster_name
	:param (str) api_class, e.g. "CoreV1Api"
	:return: (k8s.client.apis object) python k8s api client object
	"""

	# retrieve name of context that points to the given cluster
	target_context = k8s_config.context_for_cluster(cluster_name)
	if target_context == None:
		print("No valid context could be found for cluster with name", cluster_name + ".")
		print("As of most recent update, you have access to the following clusters:", k8s_config.all_cluster_names())
		return

	new_client = config.new_client_from_config(context=target_context)

	# check if given api_class is a valid k8s api class
	try:
		api_client = eval("client." + api_class + "(api_client = new_client)")
	except AttributeError as e:
		print("No known API class could be found with name", api_class + ".")
		print("API classes can be found here: https://github.com/kubernetes-client/python/blob/master/kubernetes/README.md")
		return
	return api_client
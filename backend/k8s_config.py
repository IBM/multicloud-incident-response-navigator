from typing import List, Dict
from kubernetes import client, config
import multiprocessing, time
from requests.packages import urllib3

# load kube-config when module is imported or run
config.load_kube_config()
# suppress warning when certificate-authority is not added to kubeconfig
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# cluster to context mapping
cc_mapping = {}


def test_liveness(context_name: str) -> bool:
	"""
	Makes a test request to a k8s client configured with the given context.

	Usage: Helper function, called internally.
	Arguments: (str) context_name
	Returns: (bool) whether the context returned a valid response.
	"""

	# check if there is a valid context with given name
	try:
		new_client = config.new_client_from_config(context=context_name)
	except config.config_exception.ConfigException as e:
		return False

	api_client = client.CoreV1Api(api_client = new_client)

	# check if list_namespace request throws a 404 unauthorized exception
	try:
		api_client.list_namespace()
	except client.rest.ApiException as e:
		return False

	return True


def update_available_clusters() -> Dict:
	"""
	Updates the cluster to context mapping variable with all contexts and corresponding clusters that the user is authorized to access.

	Usage: Call to refresh the list of accessible clusters.
	Arguments: None
	Returns: (dict) new cluster to context mapping
	"""

	contexts, _ = config.list_kube_config_contexts()
	new_cc_mapping = {}
	for context in contexts:
		context_name = context["name"]
		cluster_name = context["context"]["cluster"]

		# check to see if request times out (0.2 sec)
		liveness_test = multiprocessing.Process(target=test_liveness, name="list namespaces", args=(context_name,))
		liveness_test.start()
		time.sleep(1)

		# check if thread is still running (timeout) or if
		# 404 unauthorized exception was thrown
		if liveness_test.is_alive() or test_liveness(context_name) == False:
			liveness_test.terminate()
			liveness_test.join()
			continue
		else:
			new_cc_mapping[cluster_name] = context_name

	global cc_mapping
	cc_mapping = new_cc_mapping
	return new_cc_mapping


def all_cluster_names() -> List[str]:
	"""
	Wrapper function that gets all cluster names from current cluster context mapping (cc_mapping).

	Usage: Call after calling update_available_clusters() to get list of all clusters you can access right now.
	Arguments: None
	Returns: (list[str]) A list of the names of all accessible clusters.
	"""

	return list(cc_mapping.keys())


def context_for_cluster(cluster_name: str) -> str:
	"""
	Finds and returns the name of a context that points to the given cluster.

	Usage: Call when you have a cluster name and need the name of a valid context that points to that cluster.
	Arguments: 	(str) cluster_name
	Returns: 	(str) name of a context that points to the cluster,
					if such a context could be found.
				None, otherwise.
	"""
	global cc_mapping
	return cc_mapping.get(cluster_name)

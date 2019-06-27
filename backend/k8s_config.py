from kubernetes import client, config
from collections import defaultdict
import multiprocessing, time

# do this no matter what
config.load_kube_config()

# cluster to context mapping
cc_mapping = defaultdict(None)


def test_liveness(context_name):

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


def update_available_clusters():
	contexts, _ = config.list_kube_config_contexts()
	new_cc_mapping = defaultdict(None)
	for context in contexts:
		context_name = context["name"]
		cluster_name = context["context"]["cluster"]
		
		# check to see if request times out (0.2 sec)
		liveness_test = multiprocessing.Process(target=test_liveness, name="list namespaces", args=(context_name,))
		liveness_test.start()
		time.sleep(.2)

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


def all_cluster_names():
	return list(cc_mapping.keys())


def context_for_cluster(cluster_name):
	return cc_mapping[cluster_name]
from kubernetes import client, config, watch
import json, pprint
import requests
from requests.packages import urllib3
from kubernetes.client.rest import ApiException
import multiprocessing
import time

# a file for testing the k8s client (esp custom resources)
def get_app(client):
	try:
		out = client.list_cluster_custom_object('mcm.ibm.com', 'v1alpha1', 'deployables')
		print(json.dumps(out, indent=4))
	except (ApiException) as e:
		pass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# necessary when certificate-authority is not added to kubeconfig
config.load_kube_config()
contexts, active_context = config.list_kube_config_contexts()
defs = {}
# for context in contexts:
context = active_context
cluster = context["context"]["cluster"]
api_client = config.new_client_from_config(context=context['name'])
apps_client = client.AppsV1Api(api_client=api_client)
batch_client = client.BatchV1Api(api_client=api_client)
core_client = client.CoreV1Api(api_client=api_client) # usage examples https://www.programcreek.com/python/example/96328/kubernetes.client.CoreV1Api
ext_client = client.ExtensionsV1beta1Api(api_client=api_client)
customs_client = client.CustomObjectsApi(api_client=api_client)
api_ext = client.ApiextensionsV1beta1Api(api_client=api_client)
events_client = client.EventsV1beta1Api	(api_client=api_client)

# definitions = api_ext.list_custom_resource_definition(pretty=True)
print(core_client.read_namespaced_pod("busybox", "default"))

# p = multiprocessing.Process(target=get_app, args=(customs_client,))
# p.start()
# time.sleep(2)
# if p.is_alive():
# 	p.terminate()
# 	p.join()

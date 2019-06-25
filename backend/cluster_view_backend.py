from typing import List, Dict
import json
import kubernetes as k8s
from kubernetes import client, config, watch


def context_CoreV1Api_client(context_name: str):
	"""
	Wrapper for creating a k8s CoreV1Api client

	Arguments: (str) context_name
	Returns: 	kubernetes.client.apis.core_v1_api.CoreV1Api client object
					If context with given name was found in user's kube-config/contexts list.
				None, otherwise.
	"""

	if context_name == None:
		return

	# create and return CoreV1Api client obj
	try:
		new_client = config.new_client_from_config(context=context_name)
	except k8s.config.config_exception.ConfigException as e:
		print("No context", context_name, "found in kube-config/contexts list.")
	else:
		api_client = client.CoreV1Api(api_client = new_client)
		return api_client


def cluster_CoreV1Api_client(cluster_name: str):
	"""
	Wrapper for creating a k8s CoreV1Api client

	Arguments: (str) cluster_name
	Returns: 	kubernetes.client.apis.core_v1_api.CoreV1Api client object
					If context could be found that points to cluster with given name.
				None, otherwise.
	"""

	if cluster_name == None:
		return

	# find a context that points to the given cluster
	target_context = context_for_cluster(cluster_name)
	if target_context == None:
		print("No context found for cluster named", cluster_name + ".")
		return

	# create and return CoreV1Api client obj
	try:
		new_client = config.new_client_from_config(context=target_context)
	except k8s.config.config_exception.ConfigException as e:
		print("No context could found that points to cluster", cluster_name + ".")
	else:
		api_client = client.CoreV1Api(api_client = new_client)
		return api_client


def context_AppsV1Api_client(context_name: str):
	"""
	Wrapper for creating a k8s AppsV1Api client

	Arguments: (str) context_name
	Returns: 	kubernetes.client.apis.core_v1_api.AppsV1Api client object
					If context with given name was found in user's kube-config/contexts list.
				None, otherwise.
	"""

	if context_name == None:
		return

	# create and return AppsV1Api client obj
	try:
		new_client = config.new_client_from_config(context=context_name)
	except k8s.config.config_exception.ConfigException as e:
		print("No context", context_name, "found in kube-config/contexts list.")
	else:
		api_client = client.AppsV1Api(api_client = new_client)
		return api_client


def cluster_AppsV1Api_client(cluster_name):
	"""
	Wrapper for creating a k8s AppsV1Api client

	Arguments: (str) cluster_name
	Returns: 	kubernetes.client.apis.core_v1_api.AppsV1Api client object
					If context could be found that points to cluster with given name.
				None, otherwise.
	"""

	if cluster_name == None:
		return

	# find a context that points to the given cluster
	target_context = context_for_cluster(cluster_name)
	if target_context == None:
		print("No context found for cluster named", cluster_name + ".")
		return

	# create and return CoreV1Api client obj
	try:
		new_client = config.new_client_from_config(context=target_context)
	except k8s.config.config_exception.ConfigException as e:
		print("No context could found that points to cluster", cluster_name + ".")
	else:
		api_client = client.AppsV1Api(api_client = new_client)
		return api_client



def all_contexts() -> List[Dict]:
	"""
	Retrieves all contexts listed in user's kube-config

	Arguments: None
	Returns:	A list of dicts, where each dict stores information about
				a context listed in the user's kube-config.
	"""

	contexts, _ = config.list_kube_config_contexts()
	return contexts


def all_cluster_names() -> List[str]:
	"""
	Retrieves all the names of clusters that are specified in user's kube-config/contexts list

	Arguments: None
	Returns:	A list of cluster names (list[str])
					if all contexts in returned from all_contexts() are valid
				None, otherwise.
	"""

	contexts = all_contexts()
	try:
		cluster_names = [ c["context"]["cluster"] for c in contexts ]
	except KeyError as e:
		print("KeyError thrown when iterating through contexts.")
	else:
		return list(set(cluster_names))


def can_access_cluster(cluster_name):
	"""
	
	"""

	cnames = all_cluster_names()
	if cluster_name in cnames:
		return True
	return False


# returns name of first context that points to cluster
def context_for_cluster(cluster_name):
	if not can_access_cluster(cluster_name):
		return
	for context in all_contexts():
		if context["context"]["cluster"] == cluster_name:
			return context["name"]
	print("No context found for cluster", cluster_name)
	return


def cluster_namespaces(cluster_name):
	api_client = cluster_CoreV1Api_client(cluster_name)
	namespaces = api_client.list_namespace()
	return namespaces.items

def cluster_namespace_names(cluster_name):
	namespaces = cluster_namespaces(cluster_name)
	return [ ns.metadata.name for ns in namespaces ]


def namespace_deployments(namespace, cluster_name):
	api_client = cluster_AppsV1Api_client(cluster_name)
	if api_client == None:
		print("Cluster", cluster_name, "could not be accessed using your kube-config credentials.")
		return
	deploys = api_client.list_namespaced_deployment(namespace)
	return deploys.items

def namespace_deployment_names(namespace, cluster_name):
	deploys = namespace_deployments(namespace, cluster_name)
	return [ d.metadata.name for d in deploys ]


def namespace_services(namespace, cluster_name):
	api_client = cluster_CoreV1Api_client(cluster_name)
	if api_client == None:
		print("Cluster", cluster_name, "could not be accessed using your kube-config credentials.")
		return
	svcs = api_client.list_namespaced_service(namespace)
	return svcs.items

def namespace_service_names(namespace, cluster_name):
	svcs = namespace_services(namespace, cluster_name)
	return [ s.metadata.name for s in svcs ]


def namespace_stateful_sets(namespace, cluster_name):
	api_client = cluster_AppsV1Api_client(cluster_name)
	if api_client == None:
		print("Cluster", cluster_name, "could not be accessed using your kube-config credentials.")
		return
	ssets = api_client.list_namespaced_stateful_set(namespace)
	return ssets.items

def namespace_stateful_set_names(namespace, cluster_name):
	ssets = namespace_stateful_sets(namespace, cluster_name)
	return [ ss.metadata.name for ss in ssets ]


def namespace_daemon_sets(namespace, cluster_name):
	api_client = cluster_AppsV1Api_client(cluster_name)
	if api_client == None:
		print("Cluster", cluster_name, "could not be accessed using your kube-config credentials.")
		return
	dsets = api_client.list_namespaced_daemon_set(namespace)
	return dsets.items

def namespace_daemon_set_names(namespace, cluster_name):
	dsets = namespace_daemon_sets(namespace, cluster_name)
	return [ ds.metadata.name for ds in dsets ]


# need to add basic exception handling
def deployment_pods(deploy_name, namespace, cluster_name):
	AppsV1Api_client = cluster_AppsV1Api_client(cluster_name)
	CoreV1Api_client = cluster_CoreV1Api_client(cluster_name)
	deploy = AppsV1Api_client.list_namespaced_deployment(namespace, field_selector = "metadata.name=" + deploy_name).items[0]
	selector_labels = deploy.spec.selector.match_labels	# dict
	selector_str = ",".join([ key + "=" + val for key,val in selector_labels.items() ])
	selected_pods = CoreV1Api_client.list_namespaced_pod(namespace, label_selector = selector_str)
	return selected_pods.items

def deployment_pod_names(deploy_name, namespace, cluster_name):
	pods = deployment_pods(deploy_name, namespace, cluster_name)
	return [ p.metadata.name for p in pods]


def daemon_set_pods(dset_name, namespace, cluster_name):
	AppsV1Api_client = cluster_AppsV1Api_client(cluster_name)
	CoreV1Api_client = cluster_CoreV1Api_client(cluster_name)
	dset = AppsV1Api_client.list_namespaced_daemon_set(namespace, field_selector = "metadata.name=" + dset_name).items[0]
	selector_labels = dset.spec.selector.match_labels # dict
	selector_str = ",".join([ key + "=" + val for key,val in selector_labels.items() ])
	selected_pods = CoreV1Api_client.list_namespaced_pod(namespace, label_selector = selector_str)
	return selected_pods.items

def daemon_set_pod_names(dset_name, namespace, cluster_name):
	pods = daemon_set_pods(dset_name, namespace, cluster_name)
	return [ p.metadata.name for p in pods ]


def stateful_set_pods(sset_name, namespace, cluster_name):
	AppsV1Api_client = cluster_AppsV1Api_client(cluster_name)
	CoreV1Api_client = cluster_CoreV1Api_client(cluster_name)
	sset = AppsV1Api_client.list_namespaced_stateful_set(namespace, field_selector = "metadata.name=" + sset_name).items[0]
	selector_labels = sset.spec.selector.match_labels # dict
	selector_str = ",".join([ key + "=" + val for key,val in selector_labels.items() ])
	selected_pods = CoreV1Api_client.list_namespaced_pod(namespace, label_selector = selector_str)
	return selected_pods.items

def stateful_set_pod_names(sset_name, namespace, cluster_name):
	pods = stateful_set_pods(sset_name, namespace, cluster_name)
	return [ p.metadata.name for p in pods ]


def service_pods(svc_name, namespace, cluster_name):
	CoreV1Api_client = cluster_CoreV1Api_client(cluster_name)
	svc = CoreV1Api_client.list_namespaced_service(namespace, field_selector = "metadata.name=" + svc_name).items[0]
	selector_labels = svc.spec.selector # dict
	if selector_labels == None:
		return []
	selector_str = ",".join([ key + "=" + val for key,val in selector_labels.items() ])
	selected_pods = CoreV1Api_client.list_namespaced_pod(namespace, label_selector = selector_str)
	return selected_pods.items

def service_pod_names(svc_name, namespace, cluster_name):
	pods = service_pods(svc_name, namespace, cluster_name)
	return [ p.metadata.name for p in pods ]


# need to add basic exception handling
def pod_containers(pod_name, namespace, cluster_name):
	api_client = cluster_CoreV1Api_client(cluster_name)
	pod = api_client.list_namespaced_pod(namespace, field_selector = "metadata.name=" + pod_name).items[0]
	return pod.spec.containers

def pod_container_names(pod_name, namespace, cluster_name):
	containers = pod_containers(pod_name, namespace, cluster_name)
	return [ c.name for c in containers]


# need to add basic exception handling
def pod_logs(pod_name, namespace, cluster_name):
	api_client = cluster_CoreV1Api_client(cluster_name)
	logs = api_client.read_namespaced_pod_log(name=pod_name, namespace=namespace)
	return logs



# Patricia: json function here
def cluster_as_json(cluster_name):
	edges = {
				"Cluster<-Namespace": [],
				"Namespace<-Deployment": [],
				"Namespace<-DaemonSet": [],
				"Namespace<-StatefulSet": [],
				"Namespace<-Service": [],
				"Deployment<-Pod": [],
				"DaemonSet<-Pod": [],
				"StatefulSet<-Pod": [],
				"Service<-Pod": []
			}

	namespaces = cluster_namespace_names(cluster_name)
	cname = cluster_name
	for ns in namespaces:
		edges["Cluster<-Namespace"].append( [cname, ns] )

		print("working on deployments.")
		deploy_names = namespace_deployment_names(ns, cname)
		for deploy in deploy_names:
			edges["Namespace<-Deployment"].append( [ns, deploy] )
			pod_names = deployment_pod_names(deploy, ns, cname)
			for pod in pod_names:
				edges["Deployment<-Pod"].append( [deploy, pod] )

		print("working on daemon sets.")
		dset_names = namespace_daemon_set_names(ns, cname)
		for dset in dset_names:
			edges["Namespace<-DaemonSet"].append( [ns, dset] )
			pod_names = daemon_set_pod_names(dset, ns, cname)
			for pod in pod_names:
				edges["DaemonSet<-Pod"].append( [dset, pod] )

		print("working on stateful sets.")
		sset_names = namespace_stateful_set_names(ns, cname)
		for sset in sset_names:
			edges["Namespace<-StatefulSet"].append( [ns, sset] )
			pod_names = stateful_set_pod_names(sset, ns, cname)
			for pod in pod_names:
				edges["StatefulSet<-Pod"].append( [sset, pod] )

		print("working on services.")
		svc_names = namespace_service_names(ns, cname)
		for svc in svc_names:
			edges["Namespace<-Service"].append( [ns, svc] )
			pod_names = service_pod_names(svc, ns, cname)
			for pod in pod_names:
				edges["Service<-Pod"].append( [svc, pod] )

	return json.dumps(edges)



def main():
	config.load_kube_config()

if __name__ == "__main__":
	main()
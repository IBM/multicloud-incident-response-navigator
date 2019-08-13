from typing import List
import k8s_api, k8s_config, requests
import kubernetes as k8s
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# Note: call k8s_config.update_available_clusters() before use!

V1Namespace = k8s.client.models.v1_namespace.V1Namespace
V1Deployment = k8s.client.models.v1_deployment.V1Deployment
V1Service = k8s.client.models.v1_service.V1Service
V1StatefulSet = k8s.client.models.v1_stateful_set.V1StatefulSet
V1DaemonSet = k8s.client.models.v1_daemon_set.V1DaemonSet
V1Pod = k8s.client.models.v1_pod.V1Pod
V1Container = k8s.client.models.v1_container.V1Container

def mcm_clusters(cluster_names):
	"""
	Returns all MCM clusters (clusters defined using MCM cluster CRD).

	:param (List[str]) cluster_names: List of (local) cluster names
	:return: (Dict(local cluster name, cluster object)) where each item represents an MCM cluster
	"""
	myconfig = client.Configuration()
	remotes = {} # cluster_name : [ remote addresse(s) ]
	locals = {} # cluster_name : local cluster server
	cluster_objects = {}  # [ uids : cluster object ]
	remotes_by_uids = {} # cluster uid : [ remote addresses ]
	for cluster in cluster_names:
		desired_context = k8s_config.context_for_cluster(cluster)
		config.load_kube_config(context=desired_context, client_configuration=myconfig)

		# getting local address for cluster
		host = myconfig.host
		token = myconfig.api_key
		locals[cluster] = host

		response = requests.get(host+'/api', headers=token, verify=False)

		if response.status_code == 200:
			remotes[cluster] = []
			for server in response.json()["serverAddressByClientCIDRs"]:
				# getting remote addresses for cluster
				address = server["serverAddress"]
				remotes[cluster].append(address)
			api_client = k8s_api.api_client(cluster, "CustomObjectsApi")
			try:
				clusters = api_client.list_cluster_custom_object(
	    			group = "clusterregistry.k8s.io",
	    			version = "v1alpha1",
	    			plural = "clusters")["items"]

				# listing all remote clusters accessible from the current cluster
				for item in clusters:
					uid = item['metadata']['uid']
					cluster_objects [uid] = item
					remote_addresses  = []
					for ep in item['spec']['kubernetesApiEndpoints']['serverEndpoints']:
						remote_addresses.append(ep['serverAddress'])

					remotes_by_uids[uid] = remote_addresses
			except ApiException:
				pass

	clusters = {} # { local cluster name : cluster object }
	# matching clusters to remote using addresses
	for uid in remotes_by_uids: # iterating through remote clusters
		for cluster in remotes: # iterating through local clusters' remote addresses
			local = [locals[cluster].replace('https://', '')]
			if sorted(remotes[cluster]) == sorted(remotes_by_uids[uid]): # when remote address is contained in cluster object
				clusters[cluster] = cluster_objects[uid]
			elif local == remotes_by_uids[uid]: # when local host and server from the remote object matches
				clusters[cluster] = cluster_objects[uid]
	return clusters

def cluster_namespaces(cluster_name: str) -> List[V1Namespace]:
	"""
	Returns all the Namespaces that exist under the given cluster.

	:param (str) cluster_name
	:return: (List[V1Namespace]) list of namespace objects
	"""
	api_client = k8s_api.api_client(cluster_name, "CoreV1Api")
	namespaces = api_client.list_namespace()
	return namespaces.items

def namespace_deployments(namespace: str, cluster_name: str) -> List[V1Deployment]:
	"""
	Returns the Deployments that exist under the given cluster and namespace.

	:param (str) namespace
	:param (str) cluster_name: cluster that the namespace of interest is in
	:return: (List[V1Deployment]) list of deployment objects
	"""
	api_client = k8s_api.api_client(cluster_name, "AppsV1Api")
	if api_client == None:
		print("Cluster", cluster_name, "could not be accessed using your kube-config credentials.")
		return
	deploys = api_client.list_namespaced_deployment(namespace)
	return deploys.items

def namespace_services(namespace: str, cluster_name: str) -> List[V1Service]:
	"""
	Returns the Services that exist under the given cluster and namespace.

	:param (str) namespace
	:param (str) cluster_name: cluster that the namespace of interest is in
	:return: (List[V1Service]) list of service objects
	"""
	api_client = k8s_api.api_client(cluster_name, "CoreV1Api")
	if api_client == None:
		print("Cluster", cluster_name, "could not be accessed using your kube-config credentials.")
		return
	svcs = api_client.list_namespaced_service(namespace)
	return svcs.items

def namespace_stateful_sets(namespace: str, cluster_name: str) -> List[V1StatefulSet]:
	"""
	Returns the Stateful Sets that exist under the given cluster and namespace.

	:param (str) namespace
	:param (str) cluster_name: cluster that the namespace of interest is in
	:return: (List[V1StatefulSet]) list of stateful set objects
	"""
	api_client = k8s_api.api_client(cluster_name, "AppsV1Api")
	if api_client == None:
		print("Cluster", cluster_name, "could not be accessed using your kube-config credentials.")
		return
	ssets = api_client.list_namespaced_stateful_set(namespace)
	return ssets.items

def namespace_daemon_sets(namespace: str, cluster_name: str) -> List[V1DaemonSet]:
	"""
	Returns the Daemon Sets that exist under the given cluster and namespace.

	:param (str) namespace
	:param (str) cluster_name: cluster that the namespace of interest is in
	:return: (List[V1DaemonSet]) list of daemon set objects
	"""
	api_client = k8s_api.api_client(cluster_name, "AppsV1Api")
	if api_client == None:
		print("Cluster", cluster_name, "could not be accessed using your kube-config credentials.")
		return
	dsets = api_client.list_namespaced_daemon_set(namespace)
	return dsets.items

def deployment_pods(deploy_name: str, namespace: str, cluster_name: str) -> List[V1Pod]:
	"""
	Returns the Pods that exist under the given cluster, namespace, and deployment.

	:param (str) namespace
	:param (str) cluster_name: cluster that the namespace of interest is in
	:param (str) deploy_name: name of deployment of interest
	:return: (List[V1Pod]) list of pod objects
	"""
	AppsV1Api_client = k8s_api.api_client(cluster_name, "AppsV1Api")
	CoreV1Api_client = k8s_api.api_client(cluster_name, "CoreV1Api")
	deploy = AppsV1Api_client.list_namespaced_deployment(namespace, field_selector = "metadata.name=" + deploy_name).items[0]
	selector_labels = deploy.spec.selector.match_labels	# dict
	selector_str = ",".join([ key + "=" + val for key,val in selector_labels.items() ])
	selected_pods = CoreV1Api_client.list_namespaced_pod(namespace, label_selector = selector_str)
	return selected_pods.items

def daemon_set_pods(dset_name: str, namespace: str, cluster_name: str) -> List[V1Pod]:
	"""
	Returns the Pods that exist under the given cluster, namespace, and daemon set.

	:param (str) namespace
	:param (str) cluster_name: cluster that the namespace of interest is in
	:param (str) dset_name: name of daemon set of interest
	:return: (List[V1Pod]) list of pod objects
	"""
	AppsV1Api_client = k8s_api.api_client(cluster_name, "AppsV1Api")
	CoreV1Api_client = k8s_api.api_client(cluster_name, "CoreV1Api")
	dset = AppsV1Api_client.list_namespaced_daemon_set(namespace, field_selector = "metadata.name=" + dset_name).items[0]
	selector_labels = dset.spec.selector.match_labels # dict
	selector_str = ",".join([ key + "=" + val for key,val in selector_labels.items() ])
	selected_pods = CoreV1Api_client.list_namespaced_pod(namespace, label_selector = selector_str)
	return selected_pods.items

def stateful_set_pods(sset_name: str, namespace: str, cluster_name: str) -> List[V1Pod]:
	"""
	Returns the Pods that exist under the given cluster, namespace, and stateful set.

	:param (str) namespace
	:param (str) cluster_name: cluster that the namespace of interest is in
	:param (str) sset_name: name of stateful set of interest
	:return: (List[V1Pod]) list of pod objects
	"""
	AppsV1Api_client = k8s_api.api_client(cluster_name, "AppsV1Api")
	CoreV1Api_client = k8s_api.api_client(cluster_name, "CoreV1Api")
	sset = AppsV1Api_client.list_namespaced_stateful_set(namespace, field_selector = "metadata.name=" + sset_name).items[0]
	selector_labels = sset.spec.selector.match_labels # dict
	selector_str = ",".join([ key + "=" + val for key,val in selector_labels.items() ])
	selected_pods = CoreV1Api_client.list_namespaced_pod(namespace, label_selector = selector_str)
	return selected_pods.items

def service_pods(svc_name: str, namespace: str, cluster_name: str) -> List[V1Pod]:
	"""
	Returns the Pods that exist under the given cluster and namespace, and are selected by the given service.

	:param (str) namespace
	:param (str) cluster_name: cluster that the namespace of interest is in
	:param (str) svc_name: name of service of interest
	:return: (List[V1Pod]) list of pod objects
	"""
	CoreV1Api_client = k8s_api.api_client(cluster_name, "CoreV1Api")
	svc = CoreV1Api_client.list_namespaced_service(namespace, field_selector = "metadata.name=" + svc_name).items[0]
	selector_labels = svc.spec.selector # dict
	if selector_labels == None:
		return []
	selector_str = ",".join([ key + "=" + val for key,val in selector_labels.items() ])
	selected_pods = CoreV1Api_client.list_namespaced_pod(namespace, label_selector = selector_str)
	return selected_pods.items
from typing import List, Dict
import json
import kubernetes as k8s
from kubernetes import client, config
import k8s_api

# Note: call k8s_config.update_available_clusters() before use!

V1Namespace = k8s.client.models.v1_namespace.V1Namespace
V1Deployment = k8s.client.models.v1_deployment.V1Deployment
V1Service = k8s.client.models.v1_service.V1Service
V1StatefulSet = k8s.client.models.v1_stateful_set.V1StatefulSet
V1DaemonSet = k8s.client.models.v1_daemon_set.V1DaemonSet
V1Pod = k8s.client.models.v1_pod.V1Pod
V1Container = k8s.client.models.v1_container.V1Container


def cluster_namespaces(cluster_name: str) -> List[V1Namespace]:
	api_client = k8s_api.api_client(cluster_name, "CoreV1Api")
	namespaces = api_client.list_namespace()
	return namespaces.items

def cluster_namespace_names(cluster_name: str) -> List[str]:
	namespaces = cluster_namespaces(cluster_name)
	return [ ns.metadata.name for ns in namespaces ]


def namespace_deployments(namespace: str, cluster_name: str) -> List[V1Deployment]:
	api_client = k8s_api.api_client(cluster_name, "AppsV1Api")
	if api_client == None:
		print("Cluster", cluster_name, "could not be accessed using your kube-config credentials.")
		return
	deploys = api_client.list_namespaced_deployment(namespace)
	return deploys.items

def namespace_deployment_names(namespace: str, cluster_name: str) -> List[str]:
	deploys = namespace_deployments(namespace, cluster_name)
	return [ d.metadata.name for d in deploys ]


def namespace_services(namespace: str, cluster_name: str) -> List[V1Service]:
	api_client = k8s_api.api_client(cluster_name, "CoreV1Api")
	if api_client == None:
		print("Cluster", cluster_name, "could not be accessed using your kube-config credentials.")
		return
	svcs = api_client.list_namespaced_service(namespace)
	return svcs.items

def namespace_service_names(namespace: str, cluster_name: str) -> List[str]:
	svcs = namespace_services(namespace, cluster_name)
	return [ s.metadata.name for s in svcs ]


def namespace_stateful_sets(namespace: str, cluster_name: str) -> List[V1StatefulSet]:
	api_client = k8s_api.api_client(cluster_name, "AppsV1Api")
	if api_client == None:
		print("Cluster", cluster_name, "could not be accessed using your kube-config credentials.")
		return
	ssets = api_client.list_namespaced_stateful_set(namespace)
	return ssets.items

def namespace_stateful_set_names(namespace: str, cluster_name: str) -> List[str]:
	ssets = namespace_stateful_sets(namespace, cluster_name)
	return [ ss.metadata.name for ss in ssets ]


def namespace_daemon_sets(namespace: str, cluster_name: str) -> List[V1DaemonSet]:
	api_client = k8s_api.api_client(cluster_name, "AppsV1Api")
	if api_client == None:
		print("Cluster", cluster_name, "could not be accessed using your kube-config credentials.")
		return
	dsets = api_client.list_namespaced_daemon_set(namespace)
	return dsets.items

def namespace_daemon_set_names(namespace: str, cluster_name: str) -> List[str]:
	dsets = namespace_daemon_sets(namespace, cluster_name)
	return [ ds.metadata.name for ds in dsets ]


# need to add basic exception handling
def deployment_pods(deploy_name: str, namespace: str, cluster_name: str) -> List[V1Pod]:
	AppsV1Api_client = k8s_api.api_client(cluster_name, "AppsV1Api")
	CoreV1Api_client = k8s_api.api_client(cluster_name, "CoreV1Api")
	deploy = AppsV1Api_client.list_namespaced_deployment(namespace, field_selector = "metadata.name=" + deploy_name).items[0]
	selector_labels = deploy.spec.selector.match_labels	# dict
	selector_str = ",".join([ key + "=" + val for key,val in selector_labels.items() ])
	selected_pods = CoreV1Api_client.list_namespaced_pod(namespace, label_selector = selector_str)
	return selected_pods.items

def deployment_pod_names(deploy_name: str, namespace: str, cluster_name: str) -> List[str]:
	pods = deployment_pods(deploy_name, namespace, cluster_name)
	return [ p.metadata.name for p in pods]


def daemon_set_pods(dset_name: str, namespace: str, cluster_name: str) -> List[V1Pod]:
	AppsV1Api_client = k8s_api.api_client(cluster_name, "AppsV1Api")
	CoreV1Api_client = k8s_api.api_client(cluster_name, "CoreV1Api")
	dset = AppsV1Api_client.list_namespaced_daemon_set(namespace, field_selector = "metadata.name=" + dset_name).items[0]
	selector_labels = dset.spec.selector.match_labels # dict
	selector_str = ",".join([ key + "=" + val for key,val in selector_labels.items() ])
	selected_pods = CoreV1Api_client.list_namespaced_pod(namespace, label_selector = selector_str)
	return selected_pods.items

def daemon_set_pod_names(dset_name: str, namespace: str, cluster_name: str) -> List[str]:
	pods = daemon_set_pods(dset_name, namespace, cluster_name)
	return [ p.metadata.name for p in pods ]


def stateful_set_pods(sset_name: str, namespace: str, cluster_name: str) -> List[V1Pod]:
	AppsV1Api_client = k8s_api.api_client(cluster_name, "AppsV1Api")
	CoreV1Api_client = k8s_api.api_client(cluster_name, "CoreV1Api")
	sset = AppsV1Api_client.list_namespaced_stateful_set(namespace, field_selector = "metadata.name=" + sset_name).items[0]
	selector_labels = sset.spec.selector.match_labels # dict
	selector_str = ",".join([ key + "=" + val for key,val in selector_labels.items() ])
	selected_pods = CoreV1Api_client.list_namespaced_pod(namespace, label_selector = selector_str)
	return selected_pods.items

def stateful_set_pod_names(sset_name: str, namespace: str, cluster_name: str) -> List[str]:
	pods = stateful_set_pods(sset_name, namespace, cluster_name)
	return [ p.metadata.name for p in pods ]


def service_pods(svc_name: str, namespace: str, cluster_name: str) -> List[V1Pod]:
	CoreV1Api_client = k8s_api.api_client(cluster_name, "CoreV1Api")
	svc = CoreV1Api_client.list_namespaced_service(namespace, field_selector = "metadata.name=" + svc_name).items[0]
	selector_labels = svc.spec.selector # dict
	if selector_labels == None:
		return []
	selector_str = ",".join([ key + "=" + val for key,val in selector_labels.items() ])
	selected_pods = CoreV1Api_client.list_namespaced_pod(namespace, label_selector = selector_str)
	return selected_pods.items

def service_pod_names(svc_name: str, namespace: str, cluster_name: str) -> List[str]:
	pods = service_pods(svc_name, namespace, cluster_name)
	return [ p.metadata.name for p in pods ]


# need to add basic exception handling
def pod_containers(pod_name: str, namespace: str, cluster_name: str) -> List[V1Container]:
	api_client = k8s_api.api_client(cluster_name, "CoreV1Api")
	pod = api_client.list_namespaced_pod(namespace, field_selector = "metadata.name=" + pod_name).items[0]
	return pod.spec.containers

def pod_container_names(pod_name: str, namespace: str, cluster_name: str) -> List[str]:
	containers = pod_containers(pod_name, namespace, cluster_name)
	return [ c.name for c in containers]


# need to add basic exception handling
def pod_logs(pod_name: str, namespace: str, cluster_name: str) -> str:
	api_client = k8s_api.api_client(cluster_name, "CoreV1Api")
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

		# print("working on deployments.")
		deploy_names = namespace_deployment_names(ns, cname)
		for deploy in deploy_names:
			edges["Namespace<-Deployment"].append( [ns, deploy] )
			pod_names = deployment_pod_names(deploy, ns, cname)
			for pod in pod_names:
				edges["Deployment<-Pod"].append( [deploy, pod] )

		# print("working on daemon sets.")
		dset_names = namespace_daemon_set_names(ns, cname)
		for dset in dset_names:
			edges["Namespace<-DaemonSet"].append( [ns, dset] )
			pod_names = daemon_set_pod_names(dset, ns, cname)
			for pod in pod_names:
				edges["DaemonSet<-Pod"].append( [dset, pod] )

		# print("working on stateful sets.")
		sset_names = namespace_stateful_set_names(ns, cname)
		for sset in sset_names:
			edges["Namespace<-StatefulSet"].append( [ns, sset] )
			pod_names = stateful_set_pod_names(sset, ns, cname)
			for pod in pod_names:
				edges["StatefulSet<-Pod"].append( [sset, pod] )

		# print("working on services.")
		svc_names = namespace_service_names(ns, cname)
		for svc in svc_names:
			edges["Namespace<-Service"].append( [ns, svc] )
			pod_names = service_pod_names(svc, ns, cname)
			for pod in pod_names:
				edges["Service<-Pod"].append( [svc, pod] )

	# return json.dumps(edges)
	return edges
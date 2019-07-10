import clients_resources as cr
import yaml

class ResourceFiles:
	def __init__(self):
		self.clusters, self.clients, self.active_cluster= cr.get_clients()
		self.jsons  = cr.get_resources(self.clusters, self.clients, self.active_cluster)
		self.events = {}
		for cluster in self.clients:
			self.events[cluster] = {}

	def get_yaml(self, type, name, cluster):
		for resource in self.jsons[cluster][type]:
			resource_dict = resource.to_dict()
			out = yaml.dump(resource_dict)
		return out

	def get_describe(self, type, name, namespace, cluster):
		if type in ["DaemonSet", "Deployment", "ReplicaSet", "StatefulSet"]:
			client = self.clients[cluster]["apps_client"]
		elif type in ["Pod", "Service", "Event"]:
			client = self.clients[cluster]["core_client"]

		if type == "Deployment":
			return client.read_namespaced_daemon_set(name, namespace).to_dict()
		elif type == "DaemonSet":
			return client.read_namespaced_deployment(name, namespace).to_dict()
		elif type == "ReplicaSet":
			return client.read_namespaced_replica_set(name, namespace).to_dict()
		elif type == "StatefulSet":
			return client.read_namespaced_stateful_set(name, namespace).to_dict()
		elif type == "Pod":
			return client.read_namespaced_pod(name, namespace).to_dict()
		elif type == "Event":
			return client.read_namespaced_event(name, namespace).to_dict()

	def get_events(self, cluster, uid):
		return self.events.get(cluster).get(uid)

	def fetch_events(self): # fetches events for all clusters
		for cluster in self.clients:
			events = self.clients[cluster]["core_client"].list_event_for_all_namespaces().items
			for e in events:
				uid = e.involved_object.uid
				self.events[cluster][uid] = e.to_dict()

	def get_logs(self, cluster, namespace, pod_name):
		return self.clients[cluster]["core_client"].read_namespaced_pod_log(pod_name, namespace)

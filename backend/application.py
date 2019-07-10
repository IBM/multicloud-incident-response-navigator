import json, io
import subprocess,  multiprocessing
import time, datetime
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
import requests
from requests.packages import urllib3
import pprint as pretty
import resource_summaries as rs

starttimeFormat = "%Y-%m-%dT%H:%M:%SZ"
nowtimeFormat = '%Y-%m-%d %H:%M:%S.%f'
now = str(datetime.datetime.utcnow())


class Application: # gets graph for application view
	def __init__(self, clients, jsons, app_json, active_cluster, hierarchy_only = True, graph = {}, uids = {}):
		self.uid = app_json["metadata"]["uid"]
		self.name = (app_json["metadata"]["name"], "Application")
		self.active_cluster = active_cluster
		self.relations = set() # all edges, in the form of
		# ((parent resource name, parent resource type), (child resource name, child resource type))
		self.resourceSummaries = {}
		self.resource_dict = {} # { type : [resource names] }
		self.jsons, self.clients, self.graph, self.app_dict= jsons, clients, graph, app_json
		self.uids = {}
		self.relations_dict = {} # { (parent type<-child type) : [ tuples of (parent name, child name)]}
		self.resource_types = ["Application", "Deployable", "Deployment", "Service", "Pod", "ReplicaSet", "DaemonSet", "StatefulSet", "Job"]
		self.relation_types = ["Application<-Deployable", "Deployable<-Service", "Deployable<-Deployment", "Deployment<-ReplicaSet", "ReplicaSet<-Pod", "Service<-Pod", "Deployable<-Helm", "DaemonSet<-Pod", "StatefulSet<-Pod", "Job<-Pod"]

		self.dpbnames = {}
		self.deployables = {}
		self.deployments = {}

		# string sets
		self.deployment_names = set()
		self.daemonSet_names = set()
		self.replicaSets_names = set()
		self.statefulSets_names = set()
		self.jobs_names = set()
		self.edges = set()
		self.paths = { active_cluster+'_'+self.uid :"/root/" }
		self.edges.add(('root', active_cluster+'_'+self.uid, "Root<-Application"))


		for type in self.resource_types:
			self.resource_dict[type] = []
			self.resourceSummaries[type] = {}

		for type in self.relation_types:
			self.relations_dict[type] = set()


		self.service_selectors = []
		self.test_printing = False
		self.print_graph = False

		for dpb in app_json["metadata"]["annotations"]["apps.ibm.com/deployables"].split(","):
			self.dpbnames[dpb] = {}

		urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
		config.load_kube_config()
		# usage examples https://www.programcreek.com/python/example/96328/kubernetes.client.CoreV1Api

	def load_hierarchy(self):
		# Getting deployables and application as a custom resource definition
		# https://stackoverflow.com/questions/42766441/kubernetes-python-api-for-creating-custom-objects
		self.load_deployables()

		for cluster in self.clients:
			self.load_deployments(cluster)
			self.load_services(cluster)
			self.load_replicaSets(cluster)
			# the following resource types do not belong under deployables, so for the sake of not duplicating edges, they're being loaded in from cluster mode
			# self.load_daemonSets(cluster)
			# self.load_statefulSets(cluster)
			# self.load_jobs(cluster)
			self.load_pods(cluster)

		if self.print_graph:
			self.printResources()
			self.printEdges()
		return self.edges

	def load_deployables(self): # gets deployables if such a custom resource exists within this cluster
		self.dpb_list = self.app_dict["metadata"]["annotations"]['apps.ibm.com/deployables'].split(",")
		self.services = {} # service name : uid of deployable for which the service is a deployer
		self.service_uids = {}
		for cluster in self.clients:
			items = self.jsons[cluster]["Deployable"]
			for dpb in items:
				name = dpb['metadata']['name']
				uid = dpb['metadata']['uid']
				kind = dpb['spec']['deployer']['kind']
				self.deployables[name] = uid
				if kind != "helm" and (name in self.dpb_list):
					self.load_deployable(dpb, name, cluster)
					app_uid = self.active_cluster+'_'+self.uid
					dpb_uid = self.active_cluster+'_'+uid
					self.edges.add((app_uid, dpb_uid, "Application<-Deployable"))
					self.paths[dpb_uid] = self.paths[app_uid]+app_uid+'/'
					if dpb['spec']['deployer']['kind'] == "Service":
						self.services[dpb['spec']['deployer']['kube']['template']['metadata']['name']] = uid

	def load_deployable(self, dpb_json, dpb_name, cluster): # parses and stores info about an individual deployable
		self.resourceSummaries["Deployable"][dpb_name] = {}
		if dpb_name in self.dpbnames:
			dpb = (dpb_name, "Deployable")
			type = dpb_json["spec"]["deployer"]["kind"]
			deployer_name = dpb_json["spec"]["deployer"]["kube"]["template"]["metadata"]["name"]
			uid = dpb_json["metadata"]["uid"]
			self.uids[uid] = dpb
			self.dpbnames[dpb_name] = uid

			if type != "helm":
				self.relations_dict["Deployable<-"+type].add((dpb_name, dpb_name))
				self.resourceSummaries[type][deployer_name] = {}
			else:
				self.relations_dict["Deployable<-Helm"].add((dpb_name, dpb_name))

			self.relations_dict["Application<-Deployable"].add((self.name[0], dpb_name))
			self.resourceSummaries["Deployable"][dpb_name] = rs.get_deployable_summary(dpb_json)

	def load_deployments(self, cluster): # builds deployable <- deployment edges
		if self.test_printing:
			print("getting deployments")
		for d in self.jsons[cluster]["Deployment"]:
			d = d.to_dict()
			name = d["metadata"]["name"]
			dpb = (name, "Deployable")
			if name in self.dpbnames:
				dpm = (name, "Deployment")
				uid = d["metadata"]["uid"]
				self.deployment_names.add(name)
				self.relations.add((dpb, dpm))
				self.deployments[name] = uid
				self.relations_dict["Deployable<-Deployment"].add((name, name))
				self.resourceSummaries["Deployment"][name] = rs.get_deployment_summary(d)
				dpb_uid = self.active_cluster+'_'+self.deployables[name]
				dpm_uid = cluster+'_'+uid
				self.edges.add((dpb_uid, dpm_uid, "Deployable<-Deployment"))
				self.paths[dpm_uid] = self.paths[dpb_uid] + dpb_uid + "/"

	def load_services(self, cluster): # gets service-specific info and append it to self.resourceSummaries, does not build deployable <- service edges
		if self.test_printing:
			print("getting services")
		for s in self.jsons[cluster]["Service"]:
			s = s.to_dict()
			name = s["metadata"]["name"]
			dpb = (name, "Deployable")
			if (name in self.services):
				ser = (name, "Service")
				uid = s["metadata"]["uid"]
				self.service_uids[name] = uid
				selectors = s["spec"]["selector"]
				self.service_selectors.append(([(s, selectors[s]) for s in selectors.keys()], name))
				self.relations.add((dpb, ser))
				self.relations_dict["Deployable<-Service"].add((name, name))
				self.resourceSummaries["Service"][name] = rs.get_service_summary(s)
				dpb_uid = self.active_cluster+'_'+self.services[name]
				svc_uid = cluster+'_'+uid
				self.edges.add((dpb_uid, cluster+'_'+uid, "Deployable<-Service"))
				self.paths[svc_uid] = self.paths[dpb_uid] + dpb_uid + "/"


	def load_replicaSets(self, cluster): # TODO: get replica sets that were not created by a deployment, if we care about that ... ?
		if self.test_printing:
			print("getting replicaSets")
		for rep in self.jsons[cluster]["ReplicaSet"]:
			rep = rep.to_dict()
			name = rep["metadata"]["name"]
			dpm_name = rep["metadata"]["owner_references"][0]["name"]
			replica = (name, "ReplicaSet")
			if (dpm_name in self.deployment_names):
				uid = rep["metadata"]["uid"]
				ownerUID = self.resourceSummaries["Deployment"][dpm_name]["UID"]
				self.replicaSets_names.add(name)
				self.relations.add(((dpm_name, "Deployment"), replica))
				self.relations_dict["Deployment<-ReplicaSet"].add((dpm_name, name))
				self.resourceSummaries["ReplicaSet"][name] = rs.get_rs_summary(rep)
				dpm_uid = cluster+'_'+ownerUID
				rs_uid = cluster+'_'+uid
				self.edges.add((dpm_uid, rs_uid, "Deployment<-ReplicaSet"))
				self.paths[rs_uid] = self.paths[dpm_uid] + dpm_uid + "/"

	def load_pods(self, cluster): # this is where replica<-pod edges are built
		if self.test_printing:
			print("getting pods")
		for pod in self.jsons[cluster]["Pod"]:
			pod = pod.to_dict()
			pod_name = pod["metadata"]["name"]
			uid = pod["metadata"]["uid"]
			pod_uid = cluster+'_'+uid
			labels = pod["metadata"]['labels']
			ownerRefs = pod["metadata"]['owner_references']
			po = (pod_name, "Pod")
			self.uids[uid] = po
			if ownerRefs: # getting owners straight from replicat sets
				ownerKind = ownerRefs[0]["kind"]
				set_name = ownerRefs[0]["name"]
				ownerUID = ownerRefs[0]["name"]
				if ((set_name in self.replicaSets_names) or (set_name in self.statefulSets_names) or (set_name in self.daemonSet_names)):
					self.relations.add(((set_name, ownerKind), (pod_name, "Pod")))
					ownerUID = self.resourceSummaries[ownerKind][set_name]["UID"]
					self.relations_dict[ownerKind+"<-Pod"].add((set_name, pod_name))
					self.resourceSummaries["Pod"][pod_name] = rs.get_pod_summary(pod, cluster)
					set_uid = cluster+'_'+ownerUID
					self.edges.add((set_uid, pod_uid, ownerKind+"<-Pod"))
					self.paths[pod_uid] = self.paths[set_uid] + set_uid + "/"

			if labels: # getting selecting service for a pod
				labels = [(l, labels[l]) for l in labels.keys()]
				for service in self.service_selectors:
					if labels >= service[0]:
						ownerUID = self.service_uids[service[1]]
						self.relations.add(((service[1], "Service"),(pod_name, "Pod")))
						self.relations_dict["Service<-Pod"].add((service[1], pod_name))
						self.resourceSummaries["Pod"][pod_name] = rs.get_pod_summary(pod, cluster)
						for c in self.clients:
							svc_uid = c+'_'+ownerUID
							svc_path = self.paths.get(svc_uid)
							if svc_path:
								self.edges.add((svc_uid, pod_uid, "Service<-Pod"))
								self.paths[pod_uid] = svc_path + svc_uid + "/"


			else:
				if self.test_printing:
					print("don't know what drives this pod yet", pod_name)

	def load_daemonSets(self, cluster): # a bit deprecated right now, update to match replicasets when the chance comes around
		if self.test_printing:
			print("getting daemonsets")
		for ds in self.jsons[cluster]["DaemonSet"]:
			ds = ds.to_dict()
			uid = ds["metadata"]["uid"]
			name = ds["metadata"]["name"]
			self.daemonSet_names.add(name)
			# if not (self.hierarchy_only):
			ds = (name, "DaemonSet")
			self.resourceSummaries["DaemonSet"][name] = {"Name": name, "UID":uid}

	def load_statefulSets(self, cluster):
		if self.test_printing:
			print("getting statefulsets")
		for ss in self.jsons[cluster]["StatefulSet"]:
			ss = ss.to_dict()
			uid = ss["metadata"]["uid"]
			name = ss["metadata"]["name"]
			self.statefulSets_names.add(name)
			self.resourceSummaries["StatefulSet"][name] = {"Name": name, "UID":uid}

	def load_jobs(self, cluster):
		if self.test_printing:
			print("getting jobs")
		for j in self.jsons[cluster]["Job"]:
			j = j.to_dict()
			uid = j["metadata"]["uid"]
			name = j["metadata"]["name"]
			self.jobs_names.add(name)
			self.resourceSummaries["Job"][name] = {"Name": name, "UID":uid}

	def printResources(self):
		print("\nResources\n")
		for type in self.resource_dict:
			print(type, self.resource_dict[type])

	def printEdges(self):
		print("\nEdges\n")
		for e in self.relations:
			print(e[0][0] , "<--", e[1][0] + '\t\t' + e[0][1] , "<--", e[1][1])
		print()

	def generate_dicts(self):
		for key in self.relations_dict.keys():
			self.relations_dict[key] = list(self.relations_dict[key])
			app = 'app:'+ self.name[0]+ '_hierarchy-only'*(self.hierarchy_only) +'.json'
			self.app_dict = {"Resources": self.resource_dict,\
		 	"Relations": self.relations_dict, \
		 	"resourceSummaries": self.resourceSummaries,
		 	"UIDs": self.uids, "Graph": self.graph\
		 }
		return self.app_dict

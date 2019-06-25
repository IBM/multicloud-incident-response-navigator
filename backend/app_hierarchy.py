import os
import io
import json
import subprocess
import time
import datetime
import sys

cloudctl = "cloudctl mc get "
kubectl = "kubectl get "
starttimeFormat = "%Y-%m-%dT%H:%M:%SZ"
nowtimeFormat = '%Y-%m-%d %H:%M:%S.%f'
now = str(datetime.datetime.utcnow())

def generate_json(name, dict):
	with io.open(name, 'w', encoding='utf-8') as f:
		f.write(json.dumps(dict, sort_keys=True, indent=4, separators=(',', ': '), ensure_ascii=False))

def load(command):
	try:
		return subprocess.run(command.split(" "), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode('utf-8')
	except subprocess.CalledProcessError:
		pass

def pprint(d, indent=0):
   for key, value in d.items():
      print('\t' * indent + str(key))
      if isinstance(value, dict):
         pretty(value, indent+1)
      else:
         print('\t' * (indent+1) + str(value))


class Application: # gets graph for application view
	def __init__(self, name, test_printing, hierarchy_only = True):
		self.namespace = load("kubectl config view --minify --output jsonpath={..namespace}")
		self.name = (name, "Application")
		self.relations = set() # all edges, in the form of
		# ((parent resource name, parent resource type), (child resource name, child resource type))
		self.resourceSummaries = {}
		self.resource_dict = {} # { type : [resource names] }
		self.works = {}
		# TODO: since each resource also has a uid, we should use it to access the dictionary rather by (name, type) pairs
		self.relations_dict = {} # { (parent type<-child type) : [ tuples of (parent name, child name)]}
		self.resource_types = ["Application", "Deployable", "Deployment", "Service", "Pod", "ReplicaSet"]
		self.relation_types = ["Application<-Deployable", "Deployable<-Service", "Deployable<-Deployment", "Deployment<-ReplicaSet", "ReplicaSet<-Pod", "Service<-Pod", "Deployable<-Helm"]
		self.non_app_relation_types = ["DaemonSet<-Pod", "StatefulSet<-Pod", "Job<-Pod"]
		self.non_app_resource_types = ["DaemonSet", "StatefulSet", "Job"]

		self.rel_dicts = ["Deployable<-Deployer"]
		self.dpb_clusters = {}

		# string sets
		self.deployment_names = set()
		self.daemonSet_names = set()
		self.replicaSets_names = set()
		self.statefulSets_names = set()
		self.jobs_names = set()

		for type in self.resource_types:
			self.resource_dict[type] = []
			self.resourceSummaries[type] = {}

		for type in self.rel_dicts:
			self.relations_dict[type] = {}

		for type in self.relation_types:
			self.relations_dict[type] = []

		self.resource_dict["Application"] = name
		self.service_selectors = []
		self.test_printing = test_printing
		self.hierarchy_only = hierarchy_only # excludes daemonsets and everything underneath

	def check_app_availability(self):
		lines = load(kubectl + "applications").split('\n')[1:-1]
		available_apps = []
		for app in lines:
			available_apps.append(app.split()[0])

		if self.name[0] not in available_apps:
			print("Please make sure input app name exists in the current cluster (should be the hub) and namespace context, which is " + self.namespace)
			sys.exit()
		command = kubectl + "application " + self.name[0] + " -o json"
		self.dpbnames = json.loads(load(command))["metadata"]["annotations"]["apps.ibm.com/deployables"].split(",")

	def printResources(self):
		print("\nResources\n")
		for type in self.resource_dict:
			print(type, self.resource_dict[type])

	def printEdges(self):
		print("\nEdges\n")
		for e in self.relations:
			print(e[0][0] , "<--", e[1][0] + '\t\t' + e[0][1] , "<--", e[1][1])
		print()

	def getDeployments(self): # also get some deployment specific info and append it to self.resourceSummaries
		command = kubectl + "deployments -o json"
		deployments = json.loads(load(command))
		for d in deployments["items"]:
			name = d["metadata"]["name"]
			dpb = (name, "Deployable")
			if name in self.dpbnames:
				dpm = (name, "Deployment")
				uid = d["metadata"]["uid"]
				self.deployment_names.add(name)
				self.relations.add((dpb, dpm))
				self.relations_dict["Deployable<-Deployment"].append((name, name))

	def getServices(self): # also get some service-specific info and append it to self.resourceSummaries
		command = kubectl + "services -o json"
		services = json.loads(load(command))
		for s in services["items"]:
			name = s["metadata"]["name"]
			dpb = (name, "Deployable")
			if name in self.dpbnames:
				ser = (name, "Service")
				uid = s["metadata"]["uid"]
				selectors = s["spec"]["selector"]
				self.service_selectors.append((list(selectors.items()), name))
				self.relations.add((dpb, ser))
				self.relations_dict["Deployable<-Service"].append((name, name))

	def getDeployables(self):
		if self.test_printing:
			print("getting deployables", self.dpbnames)
		command = kubectl + "deployables -o json"
		deployables_json = json.loads(load(command))
		for dpb_json in deployables_json["items"]:
			dpb_name = dpb_json["metadata"]["name"]
			if dpb_name in self.dpbnames:
				dpb = (dpb_name, "Deployable")
				type = dpb_json["spec"]["deployer"]["kind"]
				if type != "helm":
					self.relations_dict["Deployable<-"+type].append((dpb_name, dpb_name))
					self.get_deployable_summary(dpb_json)
				else:
					self.relations_dict["Deployable<-Helm"].append((dpb_name, dpb_name))
					self.relations_dict["Application<-Deployable"].append((self.name[0], dpb_name))
				self.relations_dict["Deployable<-Deployer"][dpb_name] = type

		self.getWorks()

	def getReplicaSets(self): # TODO: get replica sets that were not created by a deployment, if we care about that ... ?
		if self.test_printing:
			print("getting replicaSets")
		command = kubectl + "replicasets -o json"
		allReplicas = json.loads(load(command))
		for rep in allReplicas["items"]:
			repSet = rep["metadata"]["name"]
			dpm_name = rep["metadata"]["ownerReferences"][0]["name"]
			replica = (repSet, "ReplicaSet")
			if (dpm_name in self.deployment_names):
				# self.resourceSummaries[replica[1]][replica[0]] = {}
				# command = kubectl + "rs " + repSet + " -o json"
				# rs = json.loads(load(command))
				uid = rep["metadata"]["uid"]
				self.replicaSets_names.add(repSet)
				self.relations.add(((dpm_name, "Deployment"), replica))
				self.relations_dict["Deployment<-ReplicaSet"].append((dpm_name, repSet))

	def getDaemonSets(self): # a bit deprecated right now, update to match replicasets when the chance comes around
		if self.test_printing:
			print("getting daemonsets")
		command = kubectl + "daemonsets"
		daemonsets = load(command).split("\n")
		for ds in daemonsets[1:-1]:
			name = ds.split()[0]
			command = kubectl + "ds " + name + " -o json"
			ds = json.loads(load(command))
			uid = ds["metadata"]["uid"]
			self.daemonSet_names.add(name)
			if not (self.hierarchy_only):
				ds = (name, "DaemonSet")
				# self.resourceSummaries[ds[1]][ds[0]] = {}
				self.resource_dict["DaemonSet"].append(ds)

	def getStatefulSets(self):
		if self.test_printing:
			print("getting statefulsets")
		command = kubectl + "statefulsets"
		statefulsets = load(command).split("\n")
		for ss in statefulsets[1:-1]:
			name = ss.split()[0]
			command = kubectl + "ss " + name + " -o json"
			ss = json.loads(load(command))
			self.statefulSets_names.add(name)
			self.resource_dict["StatefulSet"].append(name)

	def getJobs(self):
		if self.test_printing:
			print("getting jobs")
		command = kubectl + "jobs"
		jobs = load(command).split("\n")
		for j in jobs[1:-1]:
			name = j.split()[0]
			command = kubectl + "job " + name + " -o json"
			job = json.loads(load(command))
			self.jobs_names.add(name)
			self.resource_dict["Job"].append(name)

	def get_deployment_summary(self, json):
		name = json["metadata"]["name"]
		uid = json["metadata"]["uid"]
		creationTimeStamp = json["metadata"]["creationTimestamp"]
		namespace = json["metadata"]["namespace"]
		annotations = json["metadata"]["annotations"]
		# selectors =
		# Need to finish getting relevant summaries
		summary = { "Resource Type" : "Deployment", "Name":name, \
		"UID": uid, "Created": creationTimeStamp, "Namespace":namespace, "Labels":labels, \
		"Annotations":annotations}
		self.resourceSummaries["Deployment"][name] = summary
		return summary

	def get_deployable_summary(self, json):
		name = json["metadata"]["name"]
		uid = json["metadata"]["uid"]
		creationTimeStamp = json["metadata"]["creationTimestamp"]
		namespace = json["metadata"]["namespace"]
		labels = json["metadata"]["labels"]
		annotations = json["metadata"]["annotations"]
		summary = { "Resource Type" : "Deployable", "Name":name, \
		"UID": uid, "Created": creationTimeStamp, "Namespace":namespace, "Labels":labels, \
		"Annotations":annotations}
		self.resourceSummaries["Deployable"][name] = summary

		return summary

	def get_pod_summary(self, pod):
		ready = 0
		restarts = 0
		containers = { } # rest of the pairs are (names:images)
		for container in pod["status"]["containerStatuses"]:
			ready += container["ready"]
			restarts += container["restartCount"]
			containers[container["name"]] = container["image"]
		hostIP = pod["status"]["hostIP"]
		podIP = pod["status"]["podIP"]
		status = pod["status"]["phase"]
		startTime = pod["status"]["startTime"]
		name = pod["metadata"]["name"]

		diff = datetime.datetime.strptime(now, nowtimeFormat) - datetime.datetime.strptime(startTime, starttimeFormat)
		days, seconds = diff.days, diff.seconds
		[hours, minutes, seconds] = str(datetime.timedelta(seconds=seconds)).split(":")
		hours, minutes, seconds = int(hours), int(minutes), int(seconds)
		if not days:
			if not hours:
				age = str(minutes) +"m" + str(seconds) + "s"
			else:
				age = str(hours) +"h"
		else:
			age = str(days) +"d"
		ready = str(ready)+"/"+str(len(pod["status"]["containerStatuses"]))

		summary = { "Resource Type": "Pod", "Ready": ready, "Status": status, "Restarts": restarts, \
		"Age": age, "hostIP": hostIP, "podIP": podIP, "container_Names:Images" : containers, \
		"namespace": self.namespace}

		return summary

	def getPods(self):
		if self.test_printing:
			print("getting pods")
		# time taken before optimization, with cloudctl: 20.997277975082397
		# update: using kubectl gets runtime down to 2.1557888984680176
		# not the original intended optimization, but since lists can not be iterated over, service_selectors
		command = kubectl + "pods -o json"
		pods_json = json.loads(load(command))

		for pod in pods_json["items"]:
			pod_name = pod["metadata"]["name"]
			uid = pod["metadata"]["uid"]
			labels = pod["metadata"].get('labels')
			ownerRefs = pod["metadata"].get('ownerReferences')
			po = (pod_name, "Pod")

			if ownerRefs: # getting owners straight
				kind = ownerRefs[0]["kind"]
				set_name = ownerRefs[0]["name"]
				if ((set_name in self.replicaSets_names) or (set_name in self.statefulSets_names) or (set_name in self.daemonSet_names)):
					self.relations.add(((set_name, kind), (pod_name, "Pod")))
					self.relations_dict[kind+"<-Pod"].append((set_name, pod_name))
					self.resourceSummaries["Pod"][pod_name] = self.get_pod_summary(pod)
			elif labels: # getting selecting service
				labels = set(labels.items())
				for service in self.service_selectors:
					if list(labels) <= service[0]:
						self.relations.add(((service[1], "Service"),(pod_name, "Pod")))
						self.relations_dict["Service<-Pod"].append((service[1], pod_name))
						self.resourceSummaries["Pod"][pod_name] = self.get_pod_summary(pod)
			else:
				if self.test_printing:
					print("don't know what drives this pod yet", pod_name)

	def getFilesForCluster(self, dict): # gets & stores yamls, logs, & describe files for all cluster resources
		pprint(dict)
		for type in dict:
			if type is "Application":
				continue
			for rsc in dict[type]:
				print(type, rsc)
				command = kubectl + type + " " + rsc + " -o yaml"
				yaml = load(command)
				self.resourceSummaries[type][rsc]["Yaml"] = yaml

				if type is "Pod":
					command = "kubectl logs " + rsc
					logs = load(command)
					self.resourceSummaries[type][rsc]["logs"] = logs

				command = "kubectl describe " + type + " " + rsc
				describe = load(command)
				self.resourceSummaries[type][rsc]["Describe"] = describe

	def getYaml(self, type, resource_name):
		command = kubectl + type + " " + resource_name + " -o yaml"
		string = load(command)
		return string

	def getLogs(self, pod_name):
		command = "kubectl logs " + pod_name
		string = load(command)
		return string

	def describe(self, type, resource_name, getEvents = False):
		command = "kubectl describe " + type + " " + resource_name
		string = load(command)
		if getEvents:
			return '\n'.join(string.split("Events:")[1].split('\n')[1:-1])
		else:
			return string

	def generate_dicts(self):
		app = 'app:'+ self.name[0]+ '_hierarchy-only'*(self.hierarchy_only) +'.json'
		self.app_dict = {"Resources": self.resource_dict,\
		 "Relations": self.relations_dict, \
		 "resourceSummaries": self.resourceSummaries, "clusters": self.dpb_clusters}
		return self.app_dict

	def getGraph(self):
		start_time = time.time()
		self.check_app_availability()
		self.getDeployables()
		self.getDeployments()
		self.getServices()
		# print("\n Hub cluster resources extracted in --- %s seconds ---" % (time.time() - start_time))
		self.getReplicaSets()

		# self.getDaemonSets()
		# self.getStatefulSets()
		# self.getJobs()
		self.getPods()
		# print("\n Pods and replicasets add --- %s seconds ---" % (time.time() - start_time))

		# self.getFilesForCluster(self.resource_dict)


		# switching contexts to iks

		command = "kubectl config use-context iks-extremeblue"
		subprocess.run(command.split(), stdout=subprocess.DEVNULL)

		self.getDeployments()
		self.getServices()
		self.getReplicaSets()
		self.getPods()

		# clusterResources = []
		# for kind in self.resourceSummaries:
		# 	if kind is not "Application":
		# 		for rsc in self.resourceSummaries[kind].keys():
		# 			clusterResources[kind][rsc] = {}

		for kind in self.resourceSummaries:
			if not (self.hierarchy_only and (kind in non_hierarchy_resources)):
				if kind is not "Application":
					self.resource_dict[kind] = list(self.resourceSummaries[kind].keys())
				if self.test_printing:
					self.printResources()
					self.printEdges()

		# switching back to mycluster-context
		command = "kubectl config use-context mycluster-context"
		subprocess.run(command.split(), stdout=subprocess.DEVNULL)
		# print("\n Iks cluster with app", self.name[0], "--- %s seconds ---" % (time.time() - start_time))

	def getWorks(self):
		command = kubectl + "work --all-namespaces"
		works = load(command).split('\n')[1:-1]
		for work in works:
			cols = work.split()
			cluster, work = cols[0], cols[1]
			dpb = work.split("-"+cluster)[0]
			if dpb in self.dpbnames:
				if not self.works.get(cluster):
					self.works[cluster] = []
				self.works[cluster].append(dpb)
				self.relations_dict["Application<-Deployable"].append((self.name[0], dpb))
				if cluster not in self.dpb_clusters:
					self.dpb_clusters[cluster] = []
				self.dpb_clusters[cluster].append(dpb)

def main():
	command = kubectl + "applications"
	lines = load(command).split('\n')[1:-1]
	apps = {}
	# currently assuming that the user is logged into the hub cluster to begin with
	for line in lines:
		name = line.split()[0]
		app = Application(name, hierarchy_only = False, test_printing = False)
		app.getGraph()
		apps["App_name: "+name] = app.generate_dicts()
	generate_json("app_hierarchy.json", apps)
	# print(testApp.describe("Pod", "busybox", getEvents=True))
	# use case examples of getYaml, getLogs, and describe (logs are only available for pods)
	# testApp.getYaml("Pod", "md-bookinfo-local-cluster-7cd44fbcdc-scsb2")
	# testApp.describe("Pod","md-bookinfo-local-cluster-7cd44fbcdc-scsb2")
	# testApp.getLogs("md-bookinfo-local-cluster-7cd44fbcdc-scsb2")

if __name__ == "__main__":
	main()


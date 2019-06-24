import os
import sys
import json
import subprocess

def load(command):
	return subprocess.run(command.split(" "), stdout=subprocess.PIPE).stdout.decode('utf-8')

class Application:
	def __init__(self, name):
		self.name = (name, "Application")
		self.resources = {self.name} # all nodes of hierarchy
		self.relations = set() # all edges

		self.deployment_names = set()
		self.daemonSet_names = set()
		self.replicaSets_names = set()
		self.statefulSets_names = set()

	def printResources(self):
		print("printing resources / nodes")
		for res in self.resources:
			print(res[0], res[1])

	def printEdges(self):
		print("printing relations / edges")
		for e in self.relations:
			print(e[0] , ":", e[1])

	def getDeployables(self):
		# also gets their children, deployments and services, not including helm releases as they are about to be deprecated
		command = "cloudctl mc get application " + self.name[0] + " -o json"
		self.dpbnames = json.loads(load(command))["rows"][0]["object"]["metadata"]["annotations"]["apps.ibm.com/deployables"].split(",")
		print("getting deployables")
		command = "cloudctl mc get deployables"
		deployables = load(command).split("\n")
		for line in deployables[1:-1]:
			line = line.split()
			dpb_name = line[0]
			dpb_type = line[1]
			if dpb_name in self.dpbnames:
				dpb = (dpb_name, "Deployable")
				self.resources.add(dpb)
				self.relations.add((self.name, dpb))
				if dpb_type == "Deployment":
					dpm = (dpb_name, "Deployment")
					self.resources.add(dpm)
					self.deployment_names.add(dpb_name)
					self.relations.add((self.name, dpm))
					self.relations.add((dpb, dpm))
				elif dpb_type == "Service":
					# TODO: match labels of services to determine which pods it assigns
					ser = (dpb_name, "Service")
					self.resources.add(ser)
					self.relations.add((self.name, ser))
					self.relations.add((dpb, ser))

	def getReplicaSets(self):
		print("getting replicaSets")
		command = "cloudctl mc get replicasets"
		allReplicas = load(command).split("\n")
		for i in range (1, len(allReplicas)-1):
			dpm = "-".join(allReplicas[i].split()[1].split("-")[:-1])
			if (dpm in self.deployment_names):
				rep = allReplicas[i].split()[1]
				replica = (allReplicas[i].split()[1], "ReplicaSet")
				self.replicaSets_names.add(replica)
				self.relations.add(((dpm, "Deployment"), replica))
		# TODO: do we care about replica sets that were not created by a deployment?

	def getPods(self):
		print("getting pods")
		command = "cloudctl mc get pods"
		allPods = load(command).split("\n")
		for pod in allPods[1:-1]:
			name = "-".join(pod.split()[1].split("-")[:-1])
			pod = pod.split()[1]
			# print("pod names", name)
			if name in self.daemonSet_names:
				self.relations.add(((name, "DaemonSet"), (pod, "Pod")))
			if name in self.daemonSet_names:
				self.relations.add(((name, "DaemonSet"), (pod, "Pod")))

	def getDaemonSets(self):
		print("getting daemonsets")
		command = "cloudctl mc get daemonsets"
		daemonsets = load(command).split("\n")
		for ds in daemonsets[1:-1]:
			name = ds.split()[1]
			self.daemonSet_names.add(name)

	# def getStatefulSets(self):
	# 	print("getting statefulsets")
	# 	command = "cloudctl mc get statefulsets"
	# 	daemonsets = load(command).split("\n")
	# 	for ds in daemonsets[1:-1]:
	# 		name = ds.split()[1]
	# 		self.daemonSet_names.add(name)


def main():
	appname = "gbapp-gbapp"
	app = Application(appname)
	app.getDeployables()
	app.getReplicaSets()
	app.getDaemonSets()
	app.getPods()
	app.printResources()
	app.printEdges()

if __name__ == "__main__":
	main()

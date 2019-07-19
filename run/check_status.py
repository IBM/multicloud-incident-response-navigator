import sys, requests

def main():
	"""
	Checks whether the webserver encountered an exception when starting.
	"""

	result = requests.get("http://127.0.0.1:5000/running").json()
	if result["running"] == False:
		print("Your kube-config could not be loaded.")
		print("The following exception was thrown in the loading process:\n")
		print(result["exception"])
		print()
		sys.exit(1)


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt as e:
		sys.exit(0)
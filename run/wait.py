import sys, time, requests

def loading_dots():
	"""
	Prints three loading dots.
	"""

	for i in range(3):
		print(".", end="")
		sys.stdout.flush()
		time.sleep(0.75)

	for j in range(3):
		print("\b ", end = "\b")
		sys.stdout.flush()
		time.sleep(0.75)


def main():
	"""
	Waits for flask webserver to start, and prints loading dots in the meantime.
	"""

	i = 0
	while True:
		try:
			requests.get("http://127.0.0.1:5000/")
		except requests.exceptions.ConnectionError as e:
			if i == 0:
				print("Waiting for flask webserver to start", end = "")
				i = 1
			loading_dots()
		else:
			break


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		sys.exit(1)
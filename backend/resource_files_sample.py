import resource_files

resources = resource_files.ResourceFiles()

# sample use case of getting yamls
print(resources.get_yaml("ReplicaSet", "boisterous-shark-gbapp-frontend-8b5cc67bf", "mycluster"))

# sample use case of getting events
resources.fetch_events()
print(resources.get_events('mycluster','f7994554-91f0-11e9-b68f-0e70a6ce6d3a'))

# sample use case of getting describe info
print(resources.get_describe('Pod', 'busybox', 'default', 'mycluster'))

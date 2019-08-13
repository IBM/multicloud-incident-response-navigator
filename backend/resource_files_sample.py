import resource_files

resources = resource_files.ResourceFiles()

# sample use case of getting yamls
print(resources.get_yaml("Pod", "jumpy-shark-gbapp-frontend-844fdccf55-ggkbf", "default", "mycluster"))

# sample use case of getting events
print(resources.get_events('mycluster','default','78abd8c9-ac06-11e9-b68f-0e70a6ce6d3a'))

# sample use case of getting describe info
print(resources.get_logs('mycluster', 'default', "jumpy-shark-gbapp-frontend-844fdccf55-ggkbf"))

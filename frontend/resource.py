import helpers

class Resource:

    def __init__(self, name, type):
        self.name = name
        self.type = type

    def get_name(self):
        return self.name

    def get_type(self):
        return self.type

    def __eq__(self, other):
        if type(other) == Resource and other.get_name() == self.get_name() and other.get_type() == self.get_type():
            return True
        return False

    def __str__(self):
        return "(" + helpers.get_abbrv(self.type) + ") " + self.name

class Tags(list):

    @classmethod
    def coerce(cls, tags):
        ...

    def intersection(self, other):
        ...

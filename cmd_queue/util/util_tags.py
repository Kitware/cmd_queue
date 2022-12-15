class Tags(list):
    """
    A glorified List[str] with special extra methods
    """

    @classmethod
    def coerce(cls, tags):
        """
        Coerce the tags to a list of strings or None
        """
        if tags is None:
            self = None
        elif isinstance(tags, str):
            self = cls([tags])
        elif isinstance(tags, Tags):
            self = tags
        elif isinstance(tags, list):
            self = cls(tags)
        else:
            raise TypeError(type(tags))
        return self

    def intersection(self, other):
        import ubelt as ub
        if other is None:
            return None
        isect = self.__class__(ub.oset(self) & set(other))
        return isect

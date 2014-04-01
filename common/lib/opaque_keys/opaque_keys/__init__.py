from abc import ABCMeta, abstractmethod
from stevedore.extension import ExtensionManager


class MissingNamespaceError(Exception):
    """
    Raised to indicated that a serialized key doesn't have a parseable namespace.
    """
    pass


class InvalidKeyError(Exception):
    """
    Raised to indicated that a serialized key isn't valid (wasn't able to be parsed
    by any available providers).
    """
    pass


class OpaqueKey(object):
    """
    A base-class for implementing pluggable opaque keys. Individual key subclasses identify
    particular types of resources, without specifying the actual form of the key (or
    its serialization).

    There are two levels of expected subclasses: Key type definitions, and key implementations

    OpaqueKey
        |
    KeyType
        |
    KeyImplementation

    The KeyType base class must define the class property KEY_TYPE, which identifies
    which entry_point namespace the keys implementations should be registered with.

    The KeyImplementation classes must define CANONICAL_NAMESPACE, which identifies
    the key namespace for the particular key_implementation (when serializing).
    KeyImplementations must be registered using the CANONICAL_NAMESPACE is their
    entry_point name, but can also be registered with other names for backwards
    compatibility.
    """
    __metaclass__ = ABCMeta

    NAMESPACE_SEPARATOR = u':'

    @classmethod
    @abstractmethod
    def _from_string(cls, serialized):
        """
        Return an instance of `cls` parsed from its `serialized` form.

        Args:
            cls: The :class:`OpaqueKey` subclass.
            serialized (unicode): A serialized :class:`OpaqueKey`, with namespace already removed.

        Raises:
            InvalidKeyError: Should be raised if `serialized` is not a valid serialized key
                understood by `cls`.
        """
        raise NotImplementedError()

    @abstractmethod
    def _to_string(self):
        """
        Return a serialization of `self`.

        This serialization should not include the namespace prefix.
        """
        raise NotImplementedError()

    @classmethod
    def _separate_namespace(cls, serialized):
        """
        Return the namespace from a serialized :class:`OpaqueKey`, and
        the rest of the key.

        Args:
            serialized (unicode): A serialized :class:`OpaqueKey`.

        Raises:
            MissingNamespace: Raised when no namespace can be
                extracted from `serialized`.
        """
        namespace, _, rest = serialized.partition(cls.NAMESPACE_SEPARATOR)

        # No ':' found by partition, so it returns the input string
        if namespace == serialized:
            raise MissingNamespaceError(serialized)

        return (namespace, rest)

    @classmethod
    def drivers(cls):
        return ExtensionManager(
            cls.KEY_TYPE,
            invoke_on_load=False,
        )

    @classmethod
    def from_string(cls, serialized):
        """
        Return a :class:`OpaqueKey` object deserialized from
        the `serialized` argument.

        Args:
            serialized: A stringified form of a :class:`OpaqueKey`
        """
        if serialized is None:
            raise InvalidKeyError(serialized)

        try:
            namespace, rest = cls._separate_namespace(serialized)
        except MissingNamespaceError:
            return cls._from_string_fallback(serialized)

        try:
            return cls.drivers()[namespace].plugin._from_string(rest)
        except KeyError:
            return cls._from_string_fallback(serialized)

    @classmethod
    def _from_string_fallback(cls, serialized):
        """
        Return a :class:`OpaqueKey` object deserialized from
        the `serialized` argument.

        Args:
            serialized: A malformed serialized :class:`OpaqueKey` that
                doesn't have a valid namespace
        """
        for driver in cls.drivers():
            try:
                return driver.plugin._from_string(serialized)
            except InvalidKeyError:
                pass

        raise InvalidKeyError(serialized)

    def __unicode__(self):
        return self.NAMESPACE_SEPARATOR.join([self.CANONICAL_NAMESPACE, self._to_string()])

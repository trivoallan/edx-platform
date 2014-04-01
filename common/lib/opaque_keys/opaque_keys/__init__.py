from abc import ABCMeta, abstractmethod, abstractproperty
from copy import deepcopy
from collections import namedtuple

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


class OpaqueKeyMetaclass(ABCMeta):
    """
    Metaclass for OpaqueKeys. Automatically derives the class from a namedtuple
    with a fieldset equal to the KEY_FIELDS class attribute, if KEY_FIELDS is set.
    """
    def __new__(mcs, name, bases, attrs):
        if 'KEY_FIELDS' in attrs:
            bases = bases + (namedtuple(name, attrs['KEY_FIELDS']), )

            def __eq__(self, other):
                return self.__class__ == other.__class__ and super()
        return super(OpaqueKeyMetaclass, mcs).__new__(mcs, name, bases, attrs)

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

    The KeyImplementation classes must define CANONICAL_NAMESPACE and KEY_FIELDS.
        CANONICAL_NAMESPACE: Identifies the key namespace for the particular
            key_implementation (when serializing). KeyImplementations must be
            registered using the CANONICAL_NAMESPACE is their entry_point name,
            but can also be registered with other names for backwards compatibility.
        KEY_FIELDS: A list of attribute names that will be used to establish object
            identity. KeyImplementation instances will compare equal iff all of
            their KEY_FIELDS match, and will not compare equal to instances
            of different KeyImplementation classes (even if the KEY_FIELDS match).

    OpaqueKeys are immutable.
    """
    __metaclass__ = ABCMeta
    __slots__ = ('_initialized')

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

    def __init__(self, *args, **kwargs):
        if len(args) + len(kwargs) != len(self.KEY_FIELDS):
            raise TypeError('__init__() takes exactly {} arguments ({} given)'.format(
                len(self.KEY_FIELDS),
                len(args) + len(kwargs)
            ))

        keyed_args = dict(zip(self.KEY_FIELDS, args))

        overlapping_args = keyed_args.viewkeys() & kwargs.viewkeys()
        if overlapping_args:
            raise TypeError('__init__() got multiple values for keyword argument {!r}'.format(overlapping_args[0]))

        supplied_args = dict(keyed_args)
        supplied_args.update(kwargs)

        for key, value in supplied_args.viewitems():
            if key not in self.KEY_FIELDS:
                raise TypeError('__init__() got an unexpected argument {!r}'.format(key))

            setattr(self, key, value)
        self._initialized = True

    def replace(self, **kwargs):
        existing_values = {key: getattr(self, key) for key in self.KEY_FIELDS}
        existing_values.update(kwargs)
        return type(self)(**existing_values)

    def __setattr__(self, name, value):
        if getattr(self, '_initialized', False):
            raise AttributeError("Can't set {!r}. OpaqueKeys are immutable.".format(name))

        super(OpaqueKey, self).__setattr__(name, value)

    def __delattr__(self, name):
        raise AttributeError("Can't delete {!r}. OpaqueKeys are immutable.".format(name))

    def __unicode__(self):
        return self.NAMESPACE_SEPARATOR.join([self.CANONICAL_NAMESPACE, self._to_string()])

    def __copy__(self):
        return self.replace()

    def __deepcopy__(self, memo):
        return self.replace(**{
            key: deepcopy(getattr(self, key), memo) for key in self.KEY_FIELDS
        })

    @property
    def _key(self):
        return tuple(getattr(self, field) for field in self.KEY_FIELDS)

    def __eq__(self, other):
        return (
            type(self) == type(other) and
            self._key == other._key
        )

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self._key)

    def __repr__(self):
        return '{}({})'.format(
            self.__class__.__name__,
            ', '.join(repr(getattr(self, key)) for key in self.KEY_FIELDS)
        )

    @classmethod
    def _drivers(cls):
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
            return cls._drivers()[namespace].plugin._from_string(rest)
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
        for driver in cls._drivers():
            try:
                return driver.plugin._from_string(serialized)
            except InvalidKeyError:
                pass

        raise InvalidKeyError(serialized)

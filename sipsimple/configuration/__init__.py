import cPickle

from application.notification import NotificationCenter, NotificationData
from application.python.util import Singleton
from zope.interface import Interface


__all__ = ['ConfigurationError', 'ConfigurationBackendError', 'DuplicateSectionError', 'UnknownSectionError', 'UnknownNameError',
           'ConfigurationManager', 'DefaultValue', 'IBackend', 'Setting', 'SettingsGroup', 'SettingsObject']


## Exceptions

class ConfigurationError(Exception): pass
class ConfigurationBackendError(ConfigurationError): pass
class DuplicateSectionError(ConfigurationError): pass
class UnknownSectionError(ConfigurationError): pass
class UnknownNameError(ConfigurationError): pass


## Configuration backends

class IBackend(Interface):
    """
    Interface describing a backend used for storing and retrieving configuration
    data.

    Data is kept as name, value pairs, with pairs kept in groups called
    sections. Name, value and section names can be arbitrary strings.
    """
    def add_section(section):
        """
        Add a section with a specified name or raise DuplicateSectionError if
        the section already exists.
        """
    def delete_section(section):
        """
        Delete a section identified by a name or raise UnknownSectionError if
        the section does not exist.
        """
    def set(section, name, value):
        """
        Set a name, value pair inside a section. Will overwrite the previous
        pair, if it exists; otherwise raise UnknownSectionError if the section
        does not exist.
        """
    def delete(section, name):
        """
        Delete a name, value pair from a section or raise UnknownSectionError if
        the section does not exist.
        """
    def get(section, name):
        """
        Get the value associated to the name, in the specified section or raise
        UnknownNameError if such a name, value pair does not exist and
        UnknownSectionError if the section does not exist.
        """
    def get_names(section):
        """
        Get all the names from  the specified section or raise
        UnknownSectionError if the section does not exist.
        """
    def save():
        """
        Flush the modified name, value pairs.
        """


## ConfigurationManager

class ConfigurationManager(object):
    """
    Singleton class used for storing and retrieving options, organized in
    sections. A section contains a list of objects, each with an assigned name
    which allows access to the object.
    """
    __metaclass__ = Singleton

    def __init__(self):
        self.backend = None

    def start(self, backend=None):
        """
        Initialize the ConfigurationManager to use the specified backend. This
        method can only be called once, with an object which provides IBackend.
        The other methods of the object cannot be used unless this method was
        called.
        """
        if self.backend is not None:
            raise RuntimeError("ConfigurationManager already started")
        if backend is None:
            from sipsimple.configuration.backend.configfile import ConfigFileBackend
            backend = ConfigFileBackend()
        self.backend = backend

    def set(self, section, name, object):
        """
        Save the object with an associated name in the specified section.
        Cannot be called before start().
        """
        if self.backend is None:
            raise RuntimeError("ConfigurationManager cannot be used unless started")
        data = cPickle.dumps(object)
        try:
            self.backend.set(section, name, data)
        except UnknownSectionError:
            self.backend.add_section(section)
            self.backend.set(section, name, data)

    def delete(self, section, name):
        """
        Delete an object identified by a name in the specified section. Cannot
        be called before start().
        """
        if self.backend is None:
            raise RuntimeError("ConfigurationManager cannot be used unless started")
        self.backend.delete(section, name)

    def get(self, section, name):
        """
        Get an object identified by a name in the specified section. Raises
        UnknownNameError if such an object does not exist. Cannot be called
        before start().
        """
        if self.backend is None:
            raise RuntimeError("ConfigurationManager cannot be used unless started")
        data = self.backend.get(section, name)
        return cPickle.loads(data)

    def get_names(self, section):
        """
        Get all the names from  the specified section.
        Returns a list containing the names. Cannot be called before start().
        """
        if self.backend is None:
            raise RuntimeError("ConfigurationManager cannot be used unless started")
        return self.backend.get_names(section)


    def save(self):
        """
        Flush the modified objects. Cannot be called before start().
        """
        if self.backend is None:
            raise RuntimeError("ConfigurationManager cannot be used unless started")
        self.backend.save()


## Descriptors and base classes used for represeting configuration settings

class DefaultValue(object):
    """
    This object can be set as the value for a setting and it will reset the
    setting to the default value.
    """


class ModifiedValue(object):
    """
    Instances of this class represent the state (the old and new values) of
    settings.
    """

    __slots__ = ('old', 'new')

    def __init__(self, old, new):
        self.old = old
        self.new = new

    def __repr__(self):
        return '%s(old=%r, new=%r)' % (self.__class__.__name__, self.old, self.new)


class Setting(object):
    """
    Descriptor represeting a setting in a configuration object.

    If a setting is set to the object DefaultValue, it will be reset to the
    default. Also, only Setting attributes with nillable=True can be assigned
    the value None. All other values are passed to the type specified.
    """
    def __init__(self, type, default=None, nillable=False):
        self.type = type
        self.default = default
        self.nillable = nillable
        self.objects = {}
        self.oldobjects = {}
        self.dirty = {}

    def __get__(self, obj, objtype):
        if obj is None:
            return self
        return self.objects.get(id(obj), self.default)

    def __set__(self, obj, value):
        if value is None:
            if self.nillable:
                self.objects[id(obj)] = None
            else:
                raise ValueError("Setting attribute is not nillable")
        elif value is DefaultValue:
            if self.default is None and not self.nillable:
                raise ValueError("Setting attribute is not nillable")
            self.objects.pop(id(obj), None)
        else:
            if not isinstance(value, self.type):
                value = self.type(value)
            self.objects[id(obj)] = value
        self.dirty[id(obj)] = True

    def remove(self, obj):
        """
        Removes references to values for the specified configuration object.
        """
        self.objects.pop(id(obj), None)
        self.dirty.pop(id(obj), None)

    def isset(self, obj):
        """
        Returns True if the setting is set to a different value than the
        default on the specified configuration object.
        """
        return id(obj) in self.objects

    def isdirty(self, obj):
        """
        Returns True if the setting was changed on the specified configuration
        object.
        """
        return self.dirty.get(id(obj), False)

    def clear_dirty(self, obj):
        """
        Clears the dirty flag for this setting on the specified configuration
        object.
        """
        self.dirty.pop(id(obj), None)
        try:
            self.oldobjects[id(obj)] = self.objects[id(obj)]
        except KeyError:
            pass

    def get_old(self, obj):
        return self.oldobjects.get(id(obj), self.default)

    def undo(self, obj):
        self.dirty.pop(id(obj), None)
        self.objects[id(obj)] = self.oldobjects.setdefault(id(obj), self.default)


class SettingsState(object):
    """
    This class represents configuration objects which can be pickled and can access
    the dirty state of contained settings.
    """

    def get_modified(self):
        """
        Returns a dictionary containing the settings which have been changed.
        The keys are the full paths to the attributes (from this object), which
        are mapped to a ModifiedValue instance with references to the old and
        new values.
        """
        modified = {}
        for name in dir(self.__class__):
            attribute = getattr(self.__class__, name, None)
            if isinstance(attribute, SettingsGroupMeta):
                modified_settings = getattr(self, name).get_modified()
                modified.update(dict((name+'.'+k if k else name, v) for k,v in modified_settings.iteritems()))
            elif isinstance(attribute, Setting) and attribute.isdirty(self):
                modified[name] = ModifiedValue(old=attribute.get_old(self), new=getattr(self, name))
        return modified

    def clear_dirty(self):
        """
        Clears the dirty flag in all settings contained in this configuration
        object and all its descendents.
        """
        for name in dir(self.__class__):
            attribute = getattr(self.__class__, name, None)
            if isinstance(attribute, SettingsGroupMeta):
                getattr(self, name).clear_dirty()
            elif isinstance(attribute, Setting) and attribute.isdirty(self):
                attribute.clear_dirty(self)

    def clone(self):
        """
        Create a copy of this object and all its sub settings.
        """
        raise NotImplementedError

    def update(self, object):
        """
        Update the settings and subsettings of this settings object using the
        ones in the specified object.
        """
        raise NotImplementedError

    def __getstate__(self):
        state = {}
        for name in dir(self.__class__):
            attribute = getattr(self.__class__, name, None)
            if isinstance(attribute, SettingsGroupMeta):
                state[name] = getattr(self, name)
            elif isinstance(attribute, Setting):
                if attribute.isset(self):
                    state[name] = getattr(self, name)
        if not state:
            state['__dummy__'] = None
        return state

    def __setstate__(self, state):
        state.pop('__dummy__', None)
        for name, value in state.iteritems():
            setattr(self, name, value)
            attribute = getattr(self.__class__, name, None)
            if isinstance(attribute, Setting):
                attribute.clear_dirty(self)

    def __del__(self):
        for name in dir(self.__class__):
            attribute = getattr(self.__class__, name, None)
            if isinstance(attribute, (Setting, SettingsGroupMeta)):
                attribute.remove(self)


class SettingsGroupMeta(type):
    """
    Metaclass for SettingsGroup and its subclasses which allows them to be used
    as descriptor instances.
    """
    def __init__(cls, name, bases, dct):
        cls.objects = {}

    def __get__(cls, obj, objtype):
        if obj is None:
            return cls
        attribute = cls.objects.get(id(obj), None)
        if attribute is None:
            attribute = cls.objects.setdefault(id(obj), cls())
        return attribute

    def __set__(cls, obj, value):
        if not isinstance(value, cls):
            raise TypeError("illegal type for SettingsGroup attribute")
        cls.objects[id(obj)] = value

    def remove(self, obj):
        self.objects.pop(id(obj), None)


class SettingsGroup(SettingsState):
    """
    Base class for settings groups, i.e. non-leaf and non-root nodes in the
    configuration tree. All SettingsGroup subclasses are descriptor instances
    which return an instance of the subclass type when accessed. All
    SettingsGroup intances are created without passing any arguments to the
    constructor.

    class ContainedGroup(SettingsGroup):
        pass
    class ContainingGroup(SettingsGroup):
        subgroup = ContainedGroup
    """

    __metaclass__ = SettingsGroupMeta


class SettingsObject(SettingsState):
    """
    Subclass for top-level configuration objects. These objects are identifiable
    by either a global id (set in the __id__ attribute of the class) or a local
    id passed as the sole argument when instantiating SettingsObjects. Since
    SettingsObject is a Singleton, there is only one instance of the subclasses
    per id.

    For SettingsObject subclasses which are meant to be used exclusively with a
    local id, the class attribute __id__ should be left to the value None; if
    __init__ is defined, it would have to accept exactly one argument, id.

    The local id takes precedence over the one specified as a class attribute.

    Note: __init__ and __new__ will be called not only when a new object is
    created (i.e. there weren't any settings saved in the configuration), but
    also when the object is retrieved from the configuration.
    """

    __metaclass__ = Singleton

    __section__ = None
    __id__ = None

    def __new__(cls, id=None):
        id = id or cls.__id__
        if id is None:
            raise ValueError("id is required for instantiating %s" % cls.__name__)
        if not isinstance(id, basestring):
            raise TypeError("id needs to be a string instance")
        configuration = ConfigurationManager()
        try:
            instance = configuration.get(cls.__section__, id)
        except (UnknownSectionError, UnknownNameError):
            instance = SettingsState.__new__(cls)
        else:
            if not isinstance(instance, cls):
                # TODO: Should send a notification that this object could not be retrieved
                instance = SettingsState.__new__(cls)
        instance.__id__ = id
        return instance

    def save(self):
        """
        If the __section__ class attribute is assigned a value different from
        None, the save method will use the ConfigurationManager to store the
        object under its id in the specified section.

        This method will also post a CFGSettingsDidChange notification,
        regardless of whether the settings have been saved to persistent storage
        or not. If the save does fail, a CFGManagerSaveFailed notification is
        posted as well.
        """
        modified_settings = self.get_modified()
        if not modified_settings:
            return

        configuration = ConfigurationManager()
        notification_center = NotificationCenter()
        
        try:
            if self.__section__ is not None:
                configuration.set(self.__section__, self.__id__, self)
                configuration.save()
        except Exception, e:
            notification_center.post_notification('CFGManagerSaveFailed', sender=configuration, data=NotificationData(object=self, modified=modified_settings, exception=e))
        finally:
            notification_center.post_notification('CFGSettingsDidChange', sender=self, data=NotificationData(modified=modified_settings))
            self.clear_dirty()

    def delete(self):
        """
        Remove this object from the persistent configuration. If the __section__
        attribute is None, only removes this object from Singleton's registry.
        See the documentation in the save method for information on how the
        object is stored.
        """
        if self.__id__ is self.__class__.__id__:
            raise TypeError("cannot delete %s instance with default id" % self.__class__.__name__)
        try:
            key = [key for key, value in self.__class__._instances.iteritems() if value is self][0]
        except IndexError:
            pass
        else:
            del self.__class__._instances[key]
        if self.__section__ is None:
            return
        configuration = ConfigurationManager()
        try:
            configuration.delete(self.__section__, self.__id__)
        except UnknownSectionError:
            pass
        else:
            configuration.save()
    
    
    def clone(self, new_id):
        """
        Create a copy of this object and all its sub settings.
        """
        raise NotImplementedError



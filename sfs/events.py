import collections

import sfs.exceptions as exceptions


# Exceptions


class SubscriberExists(exceptions.SFSException):
    """Exception Class for duplicate subscriber registrations"""
    pass


# Module Variables


# Maintain a dictionary of subscribers for events
_subscribers = collections.defaultdict(list)

# Event keys
events = {
    'CLI_REGISTRY': 'cli_registry',
    'COMMAND_EXECUTION': 'cli_command_exec'
}


# Event Utils


def subscriber(key, unique=False):
    """
    Decorator to add a function as a subscriber to an event specified by 'key'
    :param key: Event key
    :param unique: Mark event key as unique, preventing addition of further subscriptions to the same key
    """

    def wrapper(fn):
        if type(_subscribers[key]) is not list:
            raise SubscriberExists(
                'A subscriber "{}" has already been registered against key: "{}"'
                    .format(_subscribers[key].__name__, key)
            )
        if unique:
            if len(_subscribers[key]) > 0:
                raise SubscriberExists(
                    'One or more subscribers have already been registered against key: "{}"'.format(key))
            _subscribers[key] = fn
        else:
            _subscribers[key].append(fn)
        return fn

    return wrapper


def command_key(command):
    """Generate event key for a CLI command"""
    return "{}_{}".format(events['COMMAND_EXECUTION'], command)


def invoke_subscribers(key, *args, **kwargs):
    """
    Invoke all subscribers added against an event specified by 'key' by passing all positional and keyword arguments
    """
    for fn in (lambda x: x if type(x) is list else [x])(_subscribers[key]):
        fn(*args, **kwargs)

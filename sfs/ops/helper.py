import functools
import sfs.log_utils as log
import sfs.events as events


def cli_command(command_key):
    """Decorator for registering and logging CLI commands"""

    def _decorator(fn):

        @functools.wraps(fn)
        @events.subscriber(events.command_key(command_key), unique=True)
        def wrapper(args):
            log.logger.debug('Executing command "%s". Args: "%s"', command_key, args)
            try:
                fn(args)
            except Exception:
                log.logger.debug('Command failed')
                raise
            else:
                log.logger.debug('Command executed')

        return wrapper

    return _decorator

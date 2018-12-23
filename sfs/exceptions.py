class SFSException(Exception):
    """Base Class for all SFS related exceptions"""
    pass


class CLIValidationException(SFSException):
    """Exception class for validation errors in CLI commands"""
    pass

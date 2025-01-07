"""Common error handling for all services"""

class ServiceError(Exception):
    """Base exception for all service errors"""
    pass

class ImageError(ServiceError):
    """Base exception for image-related errors"""
    pass

class DatabaseError(ServiceError):
    """Base exception for database-related errors"""
    pass

class BatchError(ServiceError):
    """Base exception for batch processing errors"""
    pass

class AnalyzerError(ServiceError):
    """Base exception for analyzer-related errors"""
    pass

class ConfigError(ServiceError):
    """Base exception for configuration errors"""
    pass

class RunnerError(ServiceError):
    """Base exception for service runner errors"""
    pass

class WebError(ServiceError):
    """Base exception for web interface errors"""
    pass 
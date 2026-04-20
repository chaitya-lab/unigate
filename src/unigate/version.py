"""UniGate version information."""

__version__ = "0.2.1"

VERSION = tuple(__version__.split(".")[:3])
VERSION_MAJOR = int(VERSION[0])
VERSION_MINOR = int(VERSION[1])
VERSION_PATCH = int(VERSION[2] if VERSION[2].isdigit() else 0)


def check_version_compatible(required: str) -> bool:
    """Check if current version is compatible with required version.
    
    Args:
        required: Minimum version string (e.g., "0.2.0")
        
    Returns:
        True if current version >= required version
    """
    required_parts = required.split(".")
    for i, part in enumerate(required_parts[:3]):
        current_part = VERSION[i] if i < len(VERSION) else 0
        if int(current_part or 0) < int(part or 0):
            return False
        if int(current_part or 0) > int(part or 0):
            return True
    return True
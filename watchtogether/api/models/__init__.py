def ValidValueParser(name, value, valid):
    value = value.strip()

    if value not in valid:
        raise ValueError(f'{name} must be one of : {", ".join(valid)}')

    if len(value) == 0:
        raise ValueError('{name} value cannot be empty')

    return value

from .video import *
from .video_file import *
from .subtitle import *

__all__ = [
    'VideoList', 'Video', 'VideoFile', 'Subtitle', 'SubtitleList', 'SubtitleFile'
]


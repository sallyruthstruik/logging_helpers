import sys

def to_unicode(s):
    if sys.version_info[0] < 3:
        if isinstance(s, str):
            return s.decode("utf-8")

    return s

def to_string(s):
    if sys.version_info[0] < 3:
        if isinstance(s, unicode):
            return s.encode("utf-8")

    return s

def decode_repr(s):
    if sys.version_info[0] < 3:
        return s.decode("string-escape")

    return s

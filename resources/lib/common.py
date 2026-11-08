import re

class SessionStatus:
    EMPTY = "empty"
    ACTIVE = "active"
    INACTIVE = "inactive"

class PinAction:
    RESET = 0
    INPUT = 1
    SKIP = 2

def strip_html(text):
    if not text:
        return ''
    return re.sub('<[^>]*?>', '', str(text))

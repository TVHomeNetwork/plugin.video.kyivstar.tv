import re

class SessionStatus:
    EMPTY = "empty"
    ACTIVE = "active"
    INACTIVE = "inactive"

def strip_html(text):
    return re.sub('<[^>]*?>', '', text)

"""helper types"""


def boolean(value):
    """validator for boolean type"""
    if value is True or value is False:
        result = value
    elif str(value).upper() in ('1', 'TRUE', 'T'):
        result = True
    elif str(value).upper() in ('0', 'FALSE', 'F'):
        result = False
    else:
        raise ValueError('must be a boolean')
    return result

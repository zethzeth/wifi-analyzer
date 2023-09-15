import datetime


def get_current_datetime_string(format="%Y-%m-%d--%H-%M-%S"):
    """Get the current datetime in the format 'YYYY-MM-DD--HH-MM'"""
    return datetime.datetime.now().strftime(format)

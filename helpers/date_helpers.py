import datetime


def get_current_datetime_string():
    """Get the current datetime in the format 'YYYY-MM-DD--HH-MM'"""
    return datetime.datetime.now().strftime("%Y-%m-%d--%H-%M")

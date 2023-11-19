from datetime import datetime


def get_current_datetime_string(format="%Y-%m-%d--%H-%M-%S"):
    """Get the current datetime in the format 'YYYY-MM-DD--HH-MM'"""
    return datetime.now().strftime(format)


def get_prettified_datetime_from_unix(unix_timestamp, return_format="%H:%M:%S"):
    human_readable_date = datetime.fromtimestamp(unix_timestamp)
    return human_readable_date.strftime(return_format)

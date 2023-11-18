def calculate_stats(data):
    if not data:
        return 0, 0, 0
    sorted_data = sorted(data)
    total = len(data)
    average = sum(data) / total
    mid = total // 2
    median = sorted_data[mid] if total % 2 != 0 else (sorted_data[mid - 1] + sorted_data[mid]) / 2
    return total, average, median

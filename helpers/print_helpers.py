from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)


def print_formatted(label, value, width=30):
    padded_label = label.ljust(width)
    print(f"{padded_label}{value}")


def print_color(value, color="blue"):
    if hasattr(Fore, color.upper()):
        color_code = getattr(Fore, color.upper())
        print(f"{color_code} {value}")
    else:
        print(f"Color {color} not found.")


def print_block_title(title, color="none"):
    print_divider(1, "before")
    if color != "none":
        print_color(title, color)
    else:
        print(title)
    print_divider(1, "after")


def print_divider(empty_lines=0, empty_lines_position="before"):
    if "before" in empty_lines_position.lower():
        for _ in range(empty_lines):
            print("\n")
    print("##################")
    if "after" in empty_lines_position.lower():
        for _ in range(empty_lines):
            print("\n")


def print_table_line(*args, col_widths=None):
    default_width = 20
    truncated_suffix = "..."

    # Check if custom widths are provided. If not, use default.
    if col_widths is None:
        col_widths = [default_width for _ in args]

    # Adjust each item to fit the given width.
    items = []
    for i, item in enumerate(args):
        item = str(item)
        width = col_widths[i]
        if len(item) > width:
            item = item[: width - len(truncated_suffix)] + truncated_suffix
        items.append(item.ljust(width))  # Left-align by padding with spaces.

    line = "| " + " | ".join(items) + " |"
    print(line)

    # If you want separators, you can print them like this:
    # separator = '+'.join(['-' * (w + 2) for w in col_widths])
    # print(separator)

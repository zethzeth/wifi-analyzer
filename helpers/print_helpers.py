from colorama import init, Fore

# Initialize colorama
init(autoreset=True)


def print_formatted(label, value, width=30):
    padded_label = label.ljust(width)
    print(f"{padded_label}{value}")


def print_color(value, color="blue", newline=True):
    color = color.lower()
    # Default color map
    color_map = {
        "blue": Fore.BLUE,
        "red": Fore.RED,
        "yellow": Fore.YELLOW,
        "magenta": Fore.MAGENTA,
        "white": Fore.WHITE,
        "dark": "\033[38;2;64;64;64m",
        # Add more as needed
    }

    if color in color_map:
        color_code = color_map[color]
    else:
        # Directly use color if it's a color code
        color_code = color

    end_char = "\n" if newline else ""
    print(f"{color_code}{value}", end=end_char)


def print_block_title(title, color="none", empty_lines_before=1, empty_lines_after=0):
    print_divider(empty_lines_before, "before")
    if color != "none":
        print_color(title, color)
    else:
        print(title)
    print_divider(empty_lines_after, "after")


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

    color_code = "\033[38;2;64;64;64m"
    reset_code = "\033[m"
    line = (
            f"{color_code}|{reset_code} "
            + f" {color_code}|{reset_code} ".join(items)
            + f" {color_code}|{reset_code}"
    )
    print(line)

    # If you want separators, you can print them like this:
    # separator = '+'.join(['-' * (w + 2) for w in col_widths])
    # print(separator)


# value, column_width=20, is_last, color="\033[38;2;64;64;64m"
def print_table_cell(value, column_width=20, color="white", is_last=False):
    truncated_suffix = "..."
    value_str = str(value)

    # Truncate the string to fit the width
    if len(value_str) > column_width:
        value_str = value_str[: column_width - len(truncated_suffix)] + truncated_suffix

    print_color(value_str.ljust(column_width), color=color, newline=is_last)


def print_table_header(value, column_width=20, is_last=False):
    # Print the header content
    print_color(value.ljust(column_width), color="blue", newline=is_last)


def print_table_header_line(col_widths):
    line_length = sum(col_widths)
    print_color("-" * line_length, color="white")

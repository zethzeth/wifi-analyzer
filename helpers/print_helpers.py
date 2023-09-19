from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)


def print_formatted(label, value, width=30):
    padded_label = label.ljust(width)
    print(f"{padded_label}{value}")


def print_color(value, color="blue", newline=True):
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


def print_table_ping_line(*args, col_widths=None):
    default_width = 20

    # Check if custom widths are provided. If not, use default.
    if col_widths is None:
        col_widths = [default_width for _ in args]

    # Loop through each item, adjust and color them, then print using print_table_cell
    for i, item in enumerate(args):
        width = col_widths[i]

        # Set default color to gray
        cell_color = "white"

        # Check for Succeeded color condition (index 4)
        if i == 4 and item == 0:
            cell_color = "red"

        # Check for Result color conditions (index 2)
        if i == 2:
            if item is None:
                cell_color = "red"
            else:
                try:
                    int_item = int(item)
                    if item is None or int_item > 300:
                        cell_color = "red"
                    elif int_item > 150:
                        cell_color = "yellow"
                except ValueError:
                    # If item can't be converted to an integer, use the default gray color
                    cell_color = "red"

        # Now we can directly use print_table_cell to print each cell in sequence
        is_last = i == len(args) - 1
        print_table_cell(item, is_last, column_width=width, content_color=cell_color)


def print_table_cell(
    value, is_last, column_width=20, content_color="\033[38;2;64;64;64m"
):
    truncated_suffix = "..."
    if not value:
        value_str = "None"
    else:
        value_str = str(value)

    # Truncate the string to fit the width
    if len(value_str) > column_width:
        value_str = value_str[: column_width - len(truncated_suffix)] + truncated_suffix

    # Print the left table border
    print_color("|", color="dark", newline=False)

    # Print the content
    print_color(value_str.ljust(column_width), color=content_color, newline=False)

    # If it's the last cell, print the right table border and move to the next line
    if is_last:
        print_color("|", color="dark", newline=True)


def print_table_header(value, column_width=20):
    # Print the header content
    print_color(value.ljust(column_width), color="blue", newline=False)


def print_table_headers(*args, col_widths=None):
    default_width = 20
    if col_widths is None:
        col_widths = [default_width for _ in args]

    # Print the upper border line
    line_length = sum(col_widths) + len(args) - 1  # account for '|' separators
    print_color("-" * line_length, color="white")

    # Print each header
    for i, header in enumerate(args):
        # Print the left table border
        print_color("|", color="dark", newline=False)

        # Print the header content
        print_table_header(header, col_widths[i])

    # Print the right table border and move to the next line
    print_color("|", color="dark")

    # Print the lower border line
    print_color("-" * line_length, color="white")

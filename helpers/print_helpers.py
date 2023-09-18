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


def print_table_header(*args, col_widths=None):
    default_width = 20
    truncated_suffix = "..."

    # Check if custom widths are provided. If not, use default.
    if col_widths is None:
        col_widths = [default_width for _ in args]

    # Print the top line.
    top_line = "+"
    for width in col_widths:
        top_line += "-" * (width + 2) + "+"
    # print(Style.DIM + top_line + Style.RESET_ALL)
    print(top_line)

    # Adjust each item to fit the given width.
    items = []
    for i, item in enumerate(args):
        item = str(item)
        width = col_widths[i]
        if len(item) > width:
            item = item[: width - len(truncated_suffix)] + truncated_suffix
        # Left-align by padding with spaces and apply bold and blue style.
        items.append(
            Fore.BLUE + Style.BRIGHT + item.ljust(width) + Style.RESET_ALL + Fore.RESET
        )

    line = "| " + " | ".join(items) + " |"
    print(line)

    # Print the bottom line.
    bottom_line = "+"
    for width in col_widths:
        bottom_line += "-" * (width + 2) + "+"
    print(bottom_line)


def print_table_footer(col_widths):
    if not isinstance(col_widths, list):
        raise ValueError("col_widths must be a list of column widths.")

    bottom_line = "+"
    for width in col_widths:
        bottom_line += "-" * (width + 2) + "+"
    print(bottom_line)

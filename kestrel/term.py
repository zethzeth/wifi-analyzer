import sys

COLORS = {
    'red': '\033[31m',
    'yellow': '\033[33m',
    'blue': '\033[34m',
    'magenta': '\033[35m',
    'dark': '\033[38;2;100;100;100m',
}
RESET = '\033[0m'


def color(text, name: str | None) -> str:
    if not name or not sys.stdout.isatty():
        return str(text)
    return f'{COLORS[name]}{text}{RESET}'


def block_title(title: str, color_name: str | None = None):
    print(f'\n{color("## " + title, color_name)}')


class LiveTable:
    """Fixed-width table printed one row at a time while the test runs."""

    def __init__(self, columns: list[tuple[str, int]]):
        self.widths = [width for _, width in columns]
        self.headers = [header for header, _ in columns]

    def print_header(self):
        line = '-' * sum(self.widths)
        print(line)
        print(color(self._join(self.headers), 'blue'))
        print(line)

    # Cells are plain values or (value, color_name) tuples; one print call keeps rows from interleaving across threads
    def print_row(self, *cells):
        texts, colors = zip(*(cell if isinstance(cell, tuple) else (cell, None) for cell in cells))
        padded = [color(self._fit(text, width), name) for text, width, name in zip(texts, self.widths, colors)]
        print(''.join(padded), flush=True)

    def _join(self, texts) -> str:
        return ''.join(self._fit(text, width) for text, width in zip(texts, self.widths))

    @staticmethod
    def _fit(text, width: int) -> str:
        text = str(text)
        if len(text) >= width:
            text = text[:width - 4] + '...'
        return text.ljust(width)

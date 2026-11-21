class OpenOMENError(Exception):
    """
    A failure with a message meant for the user.

    `lines` holds the full message as the CLI prints it (first line is the
    error itself, following lines are hints). `str(error)` is the first line.
    """

    def __init__(self, *lines):
        super().__init__(lines[0] if lines else "")
        self.lines = list(lines)

    @property
    def message(self):
        """ First line without a leading 'Error: ' prefix, for UIs that style errors themselves. """
        first = self.lines[0] if self.lines else ""
        return first[len("Error: "):] if first.startswith("Error: ") else first

    @property
    def hints(self):
        return self.lines[1:]

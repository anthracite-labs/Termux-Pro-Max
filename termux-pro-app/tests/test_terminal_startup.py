"""Guard the first-launch terminal renderer initialization order."""
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / 'app/src/main/java/com/anthracitelabs/termuxpro/TerminalActivity.java'


class TerminalStartup(unittest.TestCase):
    def test_text_size_initializes_renderer_before_typeface(self):
        source = SOURCE.read_text()
        creation = source.index('new TerminalView(this, null)')
        size = source.index('terminal.setTextSize(', creation)
        typeface = source.index('terminal.setTypeface(', creation)
        self.assertLess(size, typeface, 'setTypeface dereferences a null renderer on first launch')

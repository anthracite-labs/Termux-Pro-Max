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

    def test_terminal_view_can_receive_touch_focus_for_ime(self):
        source = SOURCE.read_text()
        creation = source.index('new TerminalView(this, null)')
        config = source[creation:source.index('layout.addView(terminal', creation)]
        self.assertIn('terminal.setFocusableInTouchMode(true)', config)

    def test_keyboard_button_requests_explicit_ime(self):
        source = SOURCE.read_text()
        keyboard = source[source.index('void keyboard()'):source.index('@Override protected void onDestroy()')]
        self.assertIn('showSoftInput(terminal, 0)', keyboard)

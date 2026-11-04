package com.anthracitelabs.termuxpro;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.View;
import android.view.WindowInsets;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;
import com.termux.view.TerminalView;

/** Rotation reattaches to the application session without restarting Bash. */
public final class TerminalActivity extends Activity {
    TerminalView terminal;
    private TextView status;
    private Button repair, restart;
    private TerminalApp app;
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        app = (TerminalApp)getApplication(); app.activity = new java.lang.ref.WeakReference<>(this);
        LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(Color.BLACK);
        layout.setOnApplyWindowInsetsListener((view, insets) -> {
            android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.ime());
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom); return insets;
        });
        status = new TextView(this); status.setTextColor(Color.LTGRAY); status.setText(R.string.preview);
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE); layout.addView(status);
        terminal = new TerminalView(this, null); terminal.setFocusableInTouchMode(true); terminal.setTerminalViewClient(app);
        terminal.setTextSize(app.fontPixels()); terminal.setTypeface(Typeface.MONOSPACE);
        terminal.setContentDescription(getString(R.string.terminal_description));
        layout.addView(terminal, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout keys = new LinearLayout(this);
        key(keys, R.string.escape_key, () -> app.send("\033"));
        key(keys, R.string.tab_key, () -> app.send("\t"));
        key(keys, R.string.interrupt_key, () -> app.send("\003"));
        key(keys, R.string.suspend_key, () -> app.send("\032"));
        key(keys, R.string.keyboard, this::keyboard);
        key(keys, R.string.close_session, () -> { app.closeSession(); finish(); });
        HorizontalScrollView controls = new HorizontalScrollView(this); controls.addView(keys); layout.addView(controls);
        repair = key(layout, R.string.repair, () -> app.prepare(true)); repair.setVisibility(View.GONE);
        restart = key(layout, R.string.new_session, () -> { app.session = null; app.prepare(false); }); restart.setVisibility(View.GONE);
        setContentView(layout);
        if (app.session != null) attach();
        else if (!app.preparing) app.prepare(false);
        else showStatus(getString(R.string.preparing), false);
    }
    private Button key(LinearLayout parent, int label, Runnable action) {
        Button button = new Button(this); button.setText(label); button.setContentDescription(getString(label));
        button.setMinimumHeight((int)(48 * getResources().getDisplayMetrics().density));
        button.setOnClickListener(view -> action.run()); parent.addView(button); return button;
    }
    void attach() {
        repair.setVisibility(View.GONE); restart.setVisibility(View.GONE); status.setText(R.string.preview);
        terminal.attachSession(app.session); terminal.requestFocus();
        if (app.session.getPid() == -1) finished();
    }
    void finished() {
        status.setText(getString(R.string.shell_exited, app.session.getExitStatus())); restart.setVisibility(View.VISIBLE);
    }
    void showStatus(String message, boolean failed) { status.setText(message); repair.setVisibility(failed ? View.VISIBLE : View.GONE); }
    void keyboard() {
        terminal.requestFocus();
        ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showSoftInput(terminal, 0);
    }
    @Override protected void onDestroy() {
        if (app.activity.get() == this) app.activity.clear();
        if (isFinishing()) app.closeSession();
        super.onDestroy();
    }
}

package com.anthracitelabs.termuxpro;

import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;
import android.content.Intent;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.junit.runner.RunWith;

/** Real Android startup test, independent of bundled Bash acceptance. */
@RunWith(AndroidJUnit4.class)
public final class TerminalStartupSmoke {
    @Test public void activityDisplaysTerminalView() {
        var instrumentation = InstrumentationRegistry.getInstrumentation();
        var app = (TerminalApp) instrumentation.getTargetContext().getApplicationContext();
        var activity = (TerminalActivity) instrumentation.startActivitySync(
            new Intent(app, TerminalActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        assertNotNull(activity.terminal);
        instrumentation.runOnMainSync(() -> assertTrue("Terminal view is not attached",
            activity.terminal.isAttachedToWindow()));
    }
}

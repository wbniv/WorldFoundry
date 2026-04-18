// LogViewerActivity — sibling launcher icon for the game. Reads
// wf.log from the app's external-files dir (the same dir the native
// side writes via /Android/data/org.worldfoundry.wf_game/files/wf.log)
// and shows it in a scrollable, selectable TextView. A "Clear"
// button truncates the file so the next run starts fresh.

package org.worldfoundry.wf_game;

import android.app.Activity;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;

public class LogViewerActivity extends Activity {

    private TextView logView;
    private File     logFile;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_log_viewer);

        logView = findViewById(R.id.log_view);
        logFile = new File(getExternalFilesDir(null), "wf.log");

        Button refreshBtn = findViewById(R.id.refresh_button);
        Button clearBtn   = findViewById(R.id.clear_button);

        refreshBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { loadLog(); }
        });
        clearBtn.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                if (logFile.exists()) logFile.delete();
                loadLog();
            }
        });

        loadLog();
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Refresh every time user brings the viewer forward (e.g. after a
        // game crash they alt-tab back to the log).
        loadLog();
    }

    private void loadLog() {
        StringBuilder sb = new StringBuilder();
        sb.append("log: ").append(logFile.getAbsolutePath()).append("\n");
        if (!logFile.exists()) {
            sb.append("(file doesn't exist — game never ran, "
                    + "or it crashed before android_main)\n");
        } else {
            sb.append("size: ").append(logFile.length()).append(" bytes\n");
            sb.append("---\n");
            try (FileInputStream fis = new FileInputStream(logFile)) {
                byte[] buf = new byte[Math.min((int) logFile.length(), 1024 * 1024)];
                int n = fis.read(buf);
                if (n > 0) sb.append(new String(buf, 0, n));
            } catch (IOException e) {
                sb.append("error reading log: ").append(e.getMessage());
            }
        }
        logView.setText(sb.toString());

        // Scroll to bottom — newest log content is at the end.
        ScrollView sv = findViewById(R.id.scroll);
        sv.post(new Runnable() {
            @Override public void run() { sv.fullScroll(View.FOCUS_DOWN); }
        });
    }
}

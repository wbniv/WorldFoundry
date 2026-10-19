package org.worldfoundry.wf_game.patchwork;

import android.app.Activity;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.TextView;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.URI;
import org.json.JSONObject;

/** Thin TV display. The rules, multiplayer and drawing interface remain JavaScript. */
public final class TvActivity extends Activity {
    private WebView display;
    private String origin;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        hideSystemBars();
        try {
            InputStream stream = getAssets().open("connection.json");
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            byte[] buffer = new byte[1024]; int length;
            while ((length = stream.read(buffer)) != -1) bytes.write(buffer, 0, length);
            stream.close();
            JSONObject config = new JSONObject(bytes.toString("UTF-8"));
            origin = config.getString("origin");
            boolean check = config.optBoolean("automatedCheck", false);
            display = new WebView(this);
            display.setBackgroundColor(0xffd4d9d2);
            display.getSettings().setJavaScriptEnabled(true);
            display.getSettings().setDomStorageEnabled(true);
            display.getSettings().setAllowFileAccess(false);
            display.getSettings().setAllowContentAccess(false);
            display.getSettings().setUseWideViewPort(true);
            display.getSettings().setLoadWithOverviewMode(true);
            display.setWebChromeClient(new WebChromeClient() {
                @Override public boolean onConsoleMessage(ConsoleMessage message) {
                    Log.i("QuiltNightTV", message.message()); return true;
                }
            });
            display.setWebViewClient(new WebViewClient() {
                @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap icon) {
                    Log.i("QuiltNightTV", "TV_PAGE_STARTED " + url);
                }
                @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                    return !sameOrigin(request.getUrl().toString());
                }
                @Override public void onPageFinished(WebView view, String url) {
                    Log.i("QuiltNightTV", "TV_PAGE_LOADED " + url);
                }
                @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                    Log.e("QuiltNightTV", "TV_LOAD_ERROR " + request.getUrl() + " " + error.getErrorCode() + " " + error.getDescription());
                }
                @Override public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
                    Log.e("QuiltNightTV", "TV_HTTP_ERROR " + request.getUrl() + " " + response.getStatusCode());
                }
            });
            setContentView(display);
            // Explicitly selects the Android TV display path, without booting CAF.
            String url = origin + "/receiver?display=android-tv" + (check ? "&deviceCheck=1" : "")
                + (config.optBoolean("visualCheck", false) ? "&visualCheck=1" : "");
            if (saved == null || display.restoreState(saved) == null) display.loadUrl(url);
            Log.i("QuiltNightTV", "TV_LAUNCH " + url);
            if (check) new Thread(new Runnable() { @Override public void run() {
                java.net.HttpURLConnection connection = null;
                try {
                    connection = (java.net.HttpURLConnection) new java.net.URL(origin + "/receiver").openConnection();
                    connection.setConnectTimeout(5000); connection.setReadTimeout(5000);
                    Log.i("QuiltNightTV", "TV_NETWORK_CHECK HTTP " + connection.getResponseCode());
                } catch (Exception error) {
                    Log.e("QuiltNightTV", "TV_NETWORK_CHECK_FAILED " + error);
                } finally { if (connection != null) connection.disconnect(); }
            } }, "TV-network-check").start();
        } catch (Exception error) {
            Log.e("QuiltNightTV", "TV_START_FAILED", error);
            TextView message = new TextView(this);
            message.setText("Unable to open the quilt table. Check the game server.\n" + error.getMessage());
            message.setTextSize(24); setContentView(message);
        }
    }
    private void hideSystemBars() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            getWindow().setDecorFitsSystemWindows(false);
            // getDecorView creates the decor before requesting its controller.
            // Window.getInsetsController can dereference an uncreated decor
            // when called early in onCreate, before setContentView.
            WindowInsetsController controller = getWindow().getDecorView().getWindowInsetsController();
            if (controller != null) {
                controller.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
                controller.hide(WindowInsets.Type.systemBars());
            }
        } else {
            hideLegacySystemBars();
        }
    }

    // Android 8–10 have no WindowInsetsController. Keep the compatibility
    // implementation isolated; modern devices use the supported API above.
    @SuppressWarnings("deprecation")
    private void hideLegacySystemBars() {
        getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
            | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }

    @Override public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) hideSystemBars();
    }

    private boolean sameOrigin(String url) {
        try {
            URI candidate = new URI(url), expected = new URI(origin);
            return expected.getScheme().equals(candidate.getScheme())
                && expected.getHost().equals(candidate.getHost()) && expected.getPort() == candidate.getPort();
        } catch (Exception error) { return false; }
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state); if (display != null) display.saveState(state);
    }
    @Override protected void onPause() { if (display != null) display.onPause(); super.onPause(); }
    @Override protected void onResume() { super.onResume(); if (display != null) display.onResume(); }
    @Override protected void onDestroy() { if (display != null) display.destroy(); super.onDestroy(); }
}

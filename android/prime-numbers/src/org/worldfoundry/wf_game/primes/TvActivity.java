package org.worldfoundry.wf_game.primes;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.ValueCallback;
import org.json.JSONObject;

/** Offline number chart. All educational logic lives in the bundled web app. */
public final class TvActivity extends Activity {
    private WebView display;
    private boolean ready;
    private boolean backPending;
    private String saved;
    private String pendingRestore;
    private void bars() {
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        pendingRestore = state == null ? null : state.getString("studyState");
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        display = new WebView(this);
        display.setBackgroundColor(0xff101e25);
        display.getSettings().setJavaScriptEnabled(true);
        display.getSettings().setAllowContentAccess(false);
        display.getSettings().setAllowFileAccess(true);
        display.getSettings().setAllowFileAccessFromFileURLs(false);
        display.getSettings().setAllowUniversalAccessFromFileURLs(false);
        display.getSettings().setUseWideViewPort(true);
        display.getSettings().setLoadWithOverviewMode(true);
        display.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onConsoleMessage(ConsoleMessage message) {
                String text = message.message();
                if (text.startsWith("PRIME_STATE ")) {
                    // Cache synchronously, before Android requests instance state.
                    saved = text.substring(12);
                } else Log.i("PrimeNumbersTV", text);
                return true;
            }
        });
        display.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, String url) { return true; }
            @Override public void onPageFinished(WebView view, String url) {
                ready = true;
                if (pendingRestore != null) {
                    view.evaluateJavascript("window.primeStudy.restore(JSON.parse(" + JSONObject.quote(pendingRestore) + "))", null);
                    pendingRestore = null;
                }
            }
        });
        setContentView(display); bars();
        display.loadUrl("file:///android_asset/primes/index.html");
    }
    private String key(int code) {
        switch (code) {
            case KeyEvent.KEYCODE_DPAD_UP: return "ArrowUp";
            case KeyEvent.KEYCODE_DPAD_DOWN: return "ArrowDown";
            case KeyEvent.KEYCODE_DPAD_LEFT: return "ArrowLeft";
            case KeyEvent.KEYCODE_DPAD_RIGHT: return "ArrowRight";
            case KeyEvent.KEYCODE_DPAD_CENTER:
            case KeyEvent.KEYCODE_ENTER:
            case KeyEvent.KEYCODE_BUTTON_A: return "Enter";
            default: return null;
        }
    }
    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        int code = event.getKeyCode();
        if (code == KeyEvent.KEYCODE_BACK || code == KeyEvent.KEYCODE_BUTTON_B) {
            if (event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0 && !backPending) {
                if (!ready) { finish(); return true; }
                backPending = true;
                display.evaluateJavascript("window.primeTvBack()", new ValueCallback<String>() {
                    @Override public void onReceiveValue(String result) {
                        backPending = false;
                        if (!"true".equals(result)) finish();
                    }
                });
            }
            return true;
        }
        String mapped = key(code);
        if (mapped == null) return super.dispatchKeyEvent(event);
        if (ready && (event.getAction() == KeyEvent.ACTION_DOWN || event.getAction() == KeyEvent.ACTION_UP)) {
            String type = event.getAction() == KeyEvent.ACTION_DOWN ? "keydown" : "keyup";
            display.evaluateJavascript("document.dispatchEvent(new KeyboardEvent('" + type
                + "',{key:'" + mapped + "',repeat:" + (event.getRepeatCount() > 0) + ",bubbles:true}));", null);
        }
        return true;
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        // Console state notifications keep this available synchronously.
        if (saved != null) state.putString("studyState", saved);
        super.onSaveInstanceState(state);
    }
    @Override protected void onPause() {
        if (ready) display.evaluateJavascript("window.primeTvSuspend()", null);
        display.onPause(); super.onPause();
    }
    @Override protected void onResume() { super.onResume(); if (display != null) display.onResume(); }
    @Override public void onWindowFocusChanged(boolean focus) {
        super.onWindowFocusChanged(focus);
        if (focus) bars();
        else if (ready) display.evaluateJavascript("window.primeTvSuspend()", null);
    }
    @Override protected void onDestroy() {
        ready = false;
        if (display != null) { display.destroy(); display = null; }
        super.onDestroy();
    }
}

package org.worldfoundry.wf_game.bomberman;

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

/** Offline display of the frozen solo prototype; all game rules remain JavaScript. */
public final class TvActivity extends Activity {
    private WebView display;
    private void bars() {
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN
            | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
    }
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        display = new WebView(this);
        display.setBackgroundColor(0xff0c131e);
        display.getSettings().setJavaScriptEnabled(true);
        display.getSettings().setAllowContentAccess(false);
        display.getSettings().setAllowFileAccess(true);
        display.getSettings().setUseWideViewPort(true);
        display.getSettings().setLoadWithOverviewMode(true);
        display.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onConsoleMessage(ConsoleMessage message) {
                Log.i("BombermanTV", message.message()); return true;
            }
        });
        display.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, String url) { return true; }
        });
        setContentView(display); bars();
        display.loadUrl("file:///android_asset/bomberman/solo-game.html");
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
            case KeyEvent.KEYCODE_BACK:
            case KeyEvent.KEYCODE_BUTTON_B: return "Escape";
            default: return null;
        }
    }
    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        String key = key(event.getKeyCode());
        if (key == null) return super.dispatchKeyEvent(event);
        if (event.getAction() == KeyEvent.ACTION_DOWN || event.getAction() == KeyEvent.ACTION_UP) {
            String type = event.getAction() == KeyEvent.ACTION_DOWN ? "keydown" : "keyup";
            display.evaluateJavascript("document.dispatchEvent(new KeyboardEvent('" + type
                + "',{key:'" + key + "',repeat:" + (event.getRepeatCount() > 0) + ",bubbles:true}));", null);
        }
        return true;
    }
    @Override protected void onPause() {
        display.evaluateJavascript("window.bombermanTvSuspend&&window.bombermanTvSuspend()", null);
        display.onPause(); super.onPause();
    }
    @Override protected void onResume() { super.onResume(); if (display != null) display.onResume(); }
    @Override public void onWindowFocusChanged(boolean focus) { super.onWindowFocusChanged(focus); if (focus) bars(); }
    @Override protected void onDestroy() { display.destroy(); super.onDestroy(); }
}

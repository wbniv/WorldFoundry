package org.worldfoundry.screensaver;

import android.app.Activity;
import android.app.UiModeManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.content.res.ColorStateList;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.Rect;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.StateListDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.service.dreams.DreamService;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewTreeObserver;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * The "use for screensaver" chooser: the screen a Dream's {@code settingsActivity} opens, from
 * Homeboard's Open settings button or a phone's own screensaver picker. One activity for every
 * World Foundry screensaver pack, with nothing pack-specific in it: the rows are the pack's roster
 * ({@code levels.manifest}, read by {@link LevelCatalog}), the settings provider is the one the
 * pack's Dream names in {@code org.worldfoundry.screensaver.SETTINGS_AUTHORITY}, and the choice is
 * read and written through that provider's shared {@link ChooserModel#SETTING} calls. It never
 * touches SharedPreferences, so the provider stays the only writer (LaunchModeTest).
 * docs/plans/2026-11-27-screensaver-chooser.md; android/screensaver/README.md, "Choosing the screensaver".
 *
 * <p>TV: Up and Down move, OK saves the focused level at once, Right reaches the focused row's
 * Preview and then its Undo, Back from a button returns to its row and Back from a row leaves.
 * Touch: tap a row to save; every row shows Preview. Runs in its own {@code :chooser} process.
 */
public final class ScreensaverChooserActivity extends Activity {
    private static final String TAG = "ScreensaverChooser";
    private static final String AUTHORITY_META = "org.worldfoundry.screensaver.SETTINGS_AUTHORITY";
    private static final String STATE_UNDO_VALUE = "undoValue";
    private static final String STATE_UNDO_ROW = "undoRow";
    private static final String STATE_STATUS = "status";

    private static final int BACKGROUND = 0xFF0F1419;
    private static final int TEXT = 0xFFE8EDF3;
    private static final int MUTED = 0xFF9AA7B8;
    private static final int FOCUS_FILL = 0xFFE8EEF6;
    private static final int FOCUS_TEXT = 0xFF10161D;
    private static final int ACCENT = 0xFF8AB4F8;
    private static final int ACCENT_ON_FOCUS = 0xFF1A5FD0;
    private static final int OUTLINE = 0xFF56657A;

    private final ExecutorService calls = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private final List<Row> rows = new ArrayList<>();

    private LevelCatalog roster;
    private Uri provider;
    private ChooserModel model;
    private boolean tv;
    private boolean bigText;
    private String pendingUndoValue;
    private String pendingUndoRow;
    private CharSequence status;
    private boolean busy;

    private FrameLayout root;
    private TextView notice;
    private TextView statusView;

    /** One level's row: the focusable row, its radio, name, Saved mark, Preview and Undo. */
    private static final class Row {
        String id;
        LinearLayout view;
        RadioButton radio;
        TextView chip;
        Button preview;
        Button undo;
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        UiModeManager modes = (UiModeManager) getSystemService(UI_MODE_SERVICE);
        tv = modes != null && modes.getCurrentModeType() == Configuration.UI_MODE_TYPE_TELEVISION;
        bigText = getResources().getConfiguration().fontScale >= 1.5f;
        roster = LevelCatalog.shared(() -> getApplicationContext().getAssets().open(LevelCatalog.ASSET));
        provider = Uri.parse("content://" + settingsAuthority());
        if (state != null) {
            pendingUndoValue = state.getString(STATE_UNDO_VALUE);
            pendingUndoRow = state.getString(STATE_UNDO_ROW);
            status = state.getCharSequence(STATE_STATUS);
        }
        root = new FrameLayout(this);
        root.setBackgroundColor(BACKGROUND);
        setContentView(root);
        if (tv) {
            root.getViewTreeObserver().addOnGlobalFocusChangeListener(new ViewTreeObserver.OnGlobalFocusChangeListener() {
                @Override public void onGlobalFocusChanged(View oldFocus, View newFocus) { showPreviewFor(newFocus); }
            });
        }
    }

    /** The authority the pack's Dream declares for its settings provider; {@code <package>.settings} when none does. */
    private String settingsAuthority() {
        Intent dreams = new Intent(DreamService.SERVICE_INTERFACE).setPackage(getPackageName());
        List<ResolveInfo> found = getPackageManager().queryIntentServices(dreams, PackageManager.GET_META_DATA);
        for (ResolveInfo info : found) {
            Bundle meta = info.serviceInfo == null ? null : info.serviceInfo.metaData;
            String authority = meta == null ? null : meta.getString(AUTHORITY_META);
            if (authority != null && !authority.isEmpty()) return authority;
        }
        return getPackageName() + ".settings";
    }

    @Override
    protected void onResume() {
        super.onResume();
        read();   // every time: back from a preview, or after another app (the coordinator) saved a value
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        if (model != null) {
            out.putString(STATE_UNDO_VALUE, model.undoValue());
            out.putString(STATE_UNDO_ROW, model.undoRow());
        }
        if (status != null) out.putCharSequence(STATE_STATUS, status);
    }

    @Override
    protected void onDestroy() {
        calls.shutdownNow();
        super.onDestroy();
    }

    // ---- provider calls, off the main thread ----

    private interface Done { void run(Bundle result); }

    private void call(String method, String arg, Done done, Runnable failed) {
        calls.execute(() -> {
            Bundle result;
            try {
                result = getContentResolver().call(provider, method, arg, null);
            } catch (RuntimeException error) {
                Log.e(TAG, method + " " + arg + " failed", error);
                result = null;
            }
            final Bundle answer = result;
            main.post(() -> {
                if (isFinishing() || isDestroyed()) return;
                if (answer == null) failed.run(); else done.run(answer);
            });
        });
    }

    private void read() {
        call(ChooserModel.GET_METHOD, null, result -> {
            String stored = result.getString(ChooserModel.STORED);
            if (model == null || rows.isEmpty()) {
                model = ChooserModel.of(roster, ChooserModel.SETTING, stored);
                model.restoreUndo(pendingUndoValue, pendingUndoRow);
                showList();
            } else {
                String before = model.stored();
                model.refresh(stored);
                if (before == null ? stored != null : !before.equals(stored)) status = null;   // saved elsewhere meanwhile
                bind();
            }
        }, this::showReadError);
    }

    private void choose(String id) {
        if (busy) return;
        String arg = model.choose(id);
        if (arg == null) return;   // already saved: nothing to write
        busy = true;
        call(ChooserModel.SET_METHOD, arg, result -> {
            busy = false;
            if (!result.getBoolean("saved")) { failedSave(); return; }
            model.chosen(id);
            String before = model.undoValue();
            String text = getString(R.string.chooser_status_saved, model.labelOf(id));
            if (before != null) {
                text += " " + (ChooserModel.RANDOM.equals(before)
                        ? getString(R.string.chooser_before_random)
                        : getString(R.string.chooser_before, model.labelOf(before)));
            }
            setStatus(text);
            bind();
        }, () -> { busy = false; failedSave(); });
    }

    private void undo() {
        if (busy) return;
        String arg = model.undoArgument();
        if (arg == null) return;
        busy = true;
        final String value = model.undoValue();
        final String row = model.undoRow();
        call(ChooserModel.SET_METHOD, arg, result -> {
            busy = false;
            if (!result.getBoolean("saved")) { failedSave(); return; }
            model.undone();
            setStatus(ChooserModel.RANDOM.equals(value)
                    ? getString(R.string.chooser_status_undone_random)
                    : getString(R.string.chooser_status_undone, model.labelOf(value)));
            bind();
            Row r = rowFor(row);
            if (r != null) r.view.requestFocus();
        }, () -> { busy = false; failedSave(); });
    }

    private void failedSave() {
        setStatus(getString(R.string.chooser_status_failed));
        bind();
    }

    private void preview(String id) {
        startActivity(new Intent(this, ScreensaverPreviewActivity.class).putExtra(LevelLaunch.EXTRA_LEVEL, id));
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        View focus = getCurrentFocus();
        Object owner = focus == null ? null : focus.getTag();
        if (owner instanceof Row && focus != ((Row) owner).view) {
            ((Row) owner).view.requestFocus();   // Back from Preview or Undo returns to the row
            return;
        }
        super.onBackPressed();
    }

    // ---- views ----

    private int dp(float value) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value, getResources().getDisplayMetrics()));
    }

    private TextView text(CharSequence s, float sp, int color) {
        TextView view = new TextView(this);
        view.setText(s);
        view.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        view.setTextColor(color);
        return view;
    }

    private static GradientDrawable rounded(int fill, int stroke, int strokeWidth, float radius) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(fill);
        shape.setCornerRadius(radius);
        if (strokeWidth > 0) shape.setStroke(strokeWidth, stroke);
        return shape;
    }

    /** Light when focused (TV), dimmed when pressed (touch), clear otherwise. */
    private Drawable rowBackground() {
        StateListDrawable states = new StateListDrawable();
        states.addState(new int[] {android.R.attr.state_focused}, rounded(FOCUS_FILL, 0, 0, dp(10)));
        states.addState(new int[] {android.R.attr.state_pressed}, rounded(0xFF1D2733, 0, 0, dp(10)));
        states.addState(new int[] {}, rounded(Color.TRANSPARENT, 0, 0, dp(10)));
        return states;
    }

    private static ColorStateList onRow(int focused, int normal) {
        return new ColorStateList(new int[][] {{android.R.attr.state_focused}, {}}, new int[] {focused, normal});
    }

    private Button pill(CharSequence label) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        button.setMinHeight(0);
        button.setMinimumHeight(0);
        button.setMinWidth(0);
        button.setMinimumWidth(0);
        button.setPadding(dp(14), dp(6), dp(14), dp(6));
        StateListDrawable states = new StateListDrawable();
        states.addState(new int[] {android.R.attr.state_focused}, rounded(FOCUS_FILL, FOCUS_FILL, dp(1), dp(16)));
        states.addState(new int[] {}, rounded(Color.TRANSPARENT, OUTLINE, dp(1), dp(16)));
        button.setBackground(states);
        button.setTextColor(onRow(FOCUS_TEXT, 0xFFC9D6E6));
        button.setStateListAnimator(null);
        return button;
    }

    private void showList() {
        root.removeAllViews();
        rows.clear();
        boolean wide = getResources().getConfiguration().screenWidthDp >= 720 && !bigText;
        int sideMargin = tv ? dp(48) : dp(16);
        int topMargin = tv ? dp(27) : dp(12);

        LinearLayout page = new LinearLayout(this);
        page.setOrientation(wide ? LinearLayout.HORIZONTAL : LinearLayout.VERTICAL);
        page.setPadding(sideMargin, topMargin, sideMargin, topMargin);
        root.addView(page, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        page.addView(header(wide), wide
                ? new LinearLayout.LayoutParams(dp(292), ViewGroup.LayoutParams.MATCH_PARENT)
                : new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout right = new LinearLayout(this);
        right.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams rightParams = wide
                ? new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1f)
                : new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f);
        if (wide) rightParams.leftMargin = dp(36);
        page.addView(right, rightParams);

        notice = text("", 15, 0xFFF3E3BD);
        notice.setBackground(rounded(0xFF2A2414, 0, 0, dp(8)));
        notice.setPadding(dp(12), dp(8), dp(12), dp(8));
        right.addView(notice, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        int n = model.size();
        TextView count = text(getResources().getQuantityString(R.plurals.chooser_count, n, n), 14, MUTED);
        count.setPadding(0, dp(6), 0, dp(4));
        right.addView(count);

        ScrollView scroll = new ScrollView(this);
        scroll.setVerticalFadingEdgeEnabled(true);
        scroll.setFadingEdgeLength(dp(24));
        scroll.setFillViewport(false);
        LinearLayout list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        scroll.addView(list);
        right.addView(scroll, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        for (int i = 0; i < n; i++) list.addView(row(i));
        linkFocus();

        statusView = text("", 15, 0xFFC4CFDC);
        statusView.setPadding(0, dp(8), 0, 0);
        statusView.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        right.addView(statusView);

        bind();
        rows.get(model.initialFocus()).view.requestFocus();
        showPreviewFor(getCurrentFocus());
    }

    private View header(boolean wide) {
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        if (wide) {
            ImageView icon = new ImageView(this);
            icon.setImageDrawable(getApplicationInfo().loadIcon(getPackageManager()));
            icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            column.addView(icon, new LinearLayout.LayoutParams(dp(52), dp(52)));
            TextView app = text(roster.title(), 15, MUTED);
            app.setPadding(0, dp(14), 0, dp(2));
            column.addView(app);
            TextView title = text(getString(R.string.chooser_title), 30, TEXT);
            title.setPadding(0, 0, 0, dp(10));
            column.addView(title);
            column.addView(text(getString(R.string.chooser_explain), 16, 0xFFC4CFDC));
            if (tv) {
                View spring = new View(this);
                column.addView(spring, new LinearLayout.LayoutParams(1, 0, 1f));
                String[][] hints = {
                        {"▲▼", getString(R.string.chooser_hint_choose)},
                        {"OK", getString(R.string.chooser_hint_use)},
                        {"▶", getString(R.string.chooser_hint_preview)},
                        {"⟵", getString(R.string.chooser_hint_back)}};
                for (String[] hint : hints) column.addView(text(hint[0] + "  " + hint[1], 14, MUTED));
            }
            return column;
        }
        LinearLayout line = new LinearLayout(this);
        line.setOrientation(LinearLayout.HORIZONTAL);
        line.setGravity(Gravity.CENTER_VERTICAL);
        if (!tv) {
            Button back = pill("←");
            back.setContentDescription(getString(R.string.chooser_close));
            back.setOnClickListener(v -> finish());
            back.setFocusable(false);
            LinearLayout.LayoutParams backParams = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            backParams.rightMargin = dp(12);
            line.addView(back, backParams);
        }
        LinearLayout names = new LinearLayout(this);
        names.setOrientation(LinearLayout.VERTICAL);
        names.addView(text(getString(R.string.chooser_title), bigText ? 26 : 22, TEXT));
        names.addView(text(roster.title(), 13, MUTED));
        line.addView(names);
        column.addView(line);
        if (!bigText || !tv) {
            TextView explain = text(getString(R.string.chooser_explain), 15, 0xFFC4CFDC);
            explain.setPadding(0, dp(6), 0, dp(4));
            column.addView(explain);
        }
        return column;
    }

    private View row(int i) {
        final Row r = new Row();
        r.id = model.id(i);
        r.view = new LinearLayout(this);
        r.view.setId(View.generateViewId());
        r.view.setTag(r);
        r.view.setOrientation(LinearLayout.HORIZONTAL);
        r.view.setGravity(Gravity.CENTER_VERTICAL);
        r.view.setFocusable(true);
        r.view.setClickable(true);
        r.view.setMinimumHeight(dp(tv ? 58 : 56));
        r.view.setPadding(dp(12), dp(7), dp(12), dp(7));
        r.view.setBackground(rowBackground());
        r.view.setOnClickListener(v -> choose(r.id));
        // The ScrollView scrolls a row into view when it gains focus, before showPreviewFor makes its
        // Preview visible; at a large font scale that adds a line, and the grown row would sit under the
        // bottom fade. When the focused row's height changes, bring the whole row on screen again (the
        // ScrollView's scroll-into-view leaves room for its fading edge).
        r.view.addOnLayoutChangeListener((v, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom) -> {
            if (v.hasFocus() && bottom - top != oldBottom - oldTop) {
                v.requestRectangleOnScreen(new Rect(0, 0, v.getWidth(), v.getHeight()), false);
            }
        });

        r.radio = new RadioButton(this);
        r.radio.setClickable(false);
        r.radio.setFocusable(false);
        r.radio.setDuplicateParentStateEnabled(true);
        r.radio.setButtonTintList(new ColorStateList(
                new int[][] {{android.R.attr.state_focused, android.R.attr.state_checked}, {android.R.attr.state_focused},
                        {android.R.attr.state_checked}, {}},
                new int[] {ACCENT_ON_FOCUS, 0xFF3D4A5C, ACCENT, MUTED}));
        r.radio.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        r.view.addView(r.radio, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout body = new LinearLayout(this);
        body.setOrientation(bigText ? LinearLayout.VERTICAL : LinearLayout.HORIZONTAL);
        body.setGravity(bigText ? Gravity.START : Gravity.CENTER_VERTICAL);
        body.setDuplicateParentStateEnabled(true);
        LinearLayout.LayoutParams bodyParams = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        bodyParams.leftMargin = dp(8);
        r.view.addView(body, bodyParams);

        TextView name = text(model.label(i), tv ? 19 : 17, TEXT);
        name.setTextColor(onRow(FOCUS_TEXT, TEXT));
        name.setDuplicateParentStateEnabled(true);
        body.addView(name, bigText
                ? new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
                : new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setGravity(Gravity.CENTER_VERTICAL);
        body.addView(actions);

        r.chip = text(getString(R.string.chooser_saved), 13, 0xFFA8E6B8);
        r.chip.setBackground(rounded(0xFF1D3A2B, 0xFF3F7A56, dp(1), dp(12)));
        r.chip.setPadding(dp(9), dp(2), dp(9), dp(2));
        r.chip.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        actions.addView(r.chip, spaced());

        r.preview = pill(getString(R.string.chooser_preview));
        r.preview.setId(View.generateViewId());
        r.preview.setTag(r);
        r.preview.setContentDescription(getString(R.string.chooser_preview_desc, model.label(i)));
        r.preview.setOnClickListener(v -> preview(r.id));
        actions.addView(r.preview, spaced());

        r.undo = pill(getString(R.string.chooser_undo));
        r.undo.setId(View.generateViewId());
        r.undo.setTag(r);
        r.undo.setOnClickListener(v -> undo());
        actions.addView(r.undo, spaced());

        r.view.setAccessibilityDelegate(new View.AccessibilityDelegate() {
            @Override
            public void onInitializeAccessibilityNodeInfo(View host, AccessibilityNodeInfo info) {
                super.onInitializeAccessibilityNodeInfo(host, info);
                info.setClassName(RadioButton.class.getName());
                info.setCheckable(true);
                info.setChecked(r.id.equals(model.saved()));
            }
        });
        rows.add(r);
        return r.view;
    }

    private LinearLayout.LayoutParams spaced() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.leftMargin = dp(8);
        return params;
    }

    /** Up and Down go row to row from a row or its buttons; Right walks row, Preview, Undo; Left walks back. */
    private void linkFocus() {
        for (int i = 0; i < rows.size(); i++) {
            Row r = rows.get(i);
            int up = rows.get(Math.max(0, i - 1)).view.getId();
            int down = rows.get(Math.min(rows.size() - 1, i + 1)).view.getId();
            for (View v : new View[] {r.view, r.preview, r.undo}) {
                v.setNextFocusUpId(up);
                v.setNextFocusDownId(down);
            }
            r.view.setNextFocusLeftId(r.view.getId());
            r.view.setNextFocusRightId(r.preview.getId());
            r.preview.setNextFocusLeftId(r.view.getId());
            r.preview.setNextFocusRightId(r.undo.getId());
            r.undo.setNextFocusLeftId(r.preview.getId());
            r.undo.setNextFocusRightId(r.undo.getId());
        }
    }

    /** On a TV only the row holding focus shows Preview; touch screens show it on every row. */
    private void showPreviewFor(View focus) {
        if (!tv) return;
        Object owner = focus == null ? null : focus.getTag();
        for (Row r : rows) r.preview.setVisibility(owner == r ? View.VISIBLE : View.GONE);
    }

    private Row rowFor(String id) {
        for (Row r : rows) if (r.id.equals(id)) return r;
        return null;
    }

    private void setStatus(CharSequence text) {
        status = text;
    }

    /** Marks, Undo, the notice, the status line and the spoken text, from the model. */
    private void bind() {
        if (model == null || rows.isEmpty()) return;
        String missing = model.missing();
        notice.setVisibility(missing == null ? View.GONE : View.VISIBLE);
        if (missing != null) notice.setText(getString(R.string.chooser_missing, missing));
        CharSequence line = status;
        if (line == null && model.random() && missing == null) line = getString(R.string.chooser_status_random);
        statusView.setText(line == null ? "" : line);
        int n = model.size();
        View focus = getCurrentFocus();
        for (int i = 0; i < n; i++) {
            Row r = rows.get(i);
            boolean saved = model.isSaved(i);
            r.radio.setChecked(saved);
            r.chip.setVisibility(saved ? View.VISIBLE : View.GONE);
            boolean undo = r.id.equals(model.undoRow());
            if (!undo && focus == r.undo) r.view.requestFocus();
            r.undo.setVisibility(undo ? View.VISIBLE : View.GONE);
            if (undo) {
                String value = model.undoValue();
                r.undo.setContentDescription(ChooserModel.RANDOM.equals(value)
                        ? getString(R.string.chooser_undo_desc_random)
                        : getString(R.string.chooser_undo_desc, model.labelOf(value)));
            }
            r.view.setContentDescription(getString(saved ? R.string.chooser_row_saved : R.string.chooser_row,
                    model.label(i), i + 1, n));
        }
        if (!tv) for (Row r : rows) r.preview.setVisibility(View.VISIBLE);
    }

    private void showReadError() {
        root.removeAllViews();
        rows.clear();
        model = null;
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER_VERTICAL);
        int side = tv ? dp(48) : dp(20);
        box.setPadding(side, dp(27), side, dp(27));
        box.addView(text(getString(R.string.chooser_error_title), 22, TEXT));
        TextView body = text(getString(R.string.chooser_error_body), 16, 0xFFC4CFDC);
        body.setPadding(0, dp(10), 0, dp(14));
        box.addView(body);
        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        Button retry = pill(getString(R.string.chooser_retry));
        retry.setOnClickListener(v -> read());
        Button close = pill(getString(R.string.chooser_close));
        close.setOnClickListener(v -> finish());
        buttons.addView(retry);
        buttons.addView(close, spaced());
        box.addView(buttons);
        root.addView(box, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        retry.requestFocus();
    }
}

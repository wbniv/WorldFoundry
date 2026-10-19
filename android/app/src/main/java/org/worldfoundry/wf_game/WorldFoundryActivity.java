package org.worldfoundry.wf_game;

import android.app.AlertDialog;
import android.app.NativeActivity;
import android.text.InputFilter;
import android.text.InputType;
import android.view.KeyEvent;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import java.nio.charset.StandardCharsets;

/** Android owns text input, selection and IME; native code owns the draft. */
public class WorldFoundryActivity extends NativeActivity {
    // Register the native library with this class loader for textResult JNI calls.
    static { System.loadLibrary("wf_game"); }

    private AlertDialog textDialog;
    private EditText textField;
    private long textSession;
    private int textId;
    private boolean textFinished = true;
    private int textLimit;

    private static native void textResult(long session, int field, byte[] value, boolean accept);

    // Invoked from the game thread through JNI; all Views stay on the UI thread.
    public void showPropertyText(long session, int field, String label, String value, int mode, int limit) {
        runOnUiThread(() -> {
            dismissPropertyTextNow();
            if (isFinishing() || isDestroyed()) return;
            textSession = session;
            textId = field;
            textFinished = false;
            textLimit = Math.max(1, Math.min(65536, limit));
            // Use the dialog's dark theme, rather than NativeActivity's light context.
            AlertDialog.Builder builder = new AlertDialog.Builder(this, android.R.style.Theme_Material_Dialog_Alert);
            textField = new EditText(builder.getContext());
            textField.setTextColor(0xffedf4f4);
            textField.setHintTextColor(0xffb3c6cf);
            textField.setBackgroundColor(0xff243c48);
            textField.setHighlightColor(0xff477b70);
            textField.setFilters(new InputFilter[]{new InputFilter.LengthFilter(textLimit)});
            boolean multiline = mode == 2;
            int type = InputType.TYPE_CLASS_TEXT;
            if (mode == 1) type = InputType.TYPE_CLASS_NUMBER;
            else if (mode == 3) type = InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_SIGNED;
            else if (mode == 4) type = InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_SIGNED | InputType.TYPE_NUMBER_FLAG_DECIMAL;
            else if (multiline) type |= InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES;
            textField.setInputType(type);
            textField.setSingleLine(!multiline);
            if (multiline) { textField.setMinLines(3); textField.setMaxLines(6); }
            textField.setContentDescription(label);
            textField.setText(value);
            textField.setSelectAllOnFocus(true);
            textField.setImeOptions(multiline ? EditorInfo.IME_FLAG_NO_ENTER_ACTION : EditorInfo.IME_ACTION_DONE);
            textField.setPrivateImeOptions("horizontalAlignment=center");
            int inset = Math.round(24 * getResources().getDisplayMetrics().density);
            textField.setPadding(inset, inset / 2, inset, inset / 2);
            textField.setOnEditorActionListener((view, action, event) -> {
                if (!multiline && (action == EditorInfo.IME_ACTION_DONE || (event != null && event.getKeyCode() == KeyEvent.KEYCODE_ENTER))) { finishText(true); return true; }
                return false;
            });
            textDialog = builder.setTitle(label).setView(textField)
                    .setPositiveButton("Done", null)
                    .setNegativeButton("Cancel", (dialog, which) -> finishText(false))
                    .create();
            textDialog.setCanceledOnTouchOutside(false);
            // Physical/ADB typing may arrive while D-pad navigation focuses a
            // dialog button. Printable keys still belong to the text field.
            textDialog.setOnKeyListener((dialog, code, event) -> {
                if (event.getAction() == KeyEvent.ACTION_DOWN && event.isPrintingKey()
                        && event.getUnicodeChar() >= 32 && !textField.hasFocus()) {
                    textField.requestFocus();
                    return textField.onKeyDown(code, event);
                }
                return false;
            });
            // IME handles its first back press; dialog cancellation retains text.
            textDialog.setOnCancelListener(dialog -> finishText(true, false));
            textDialog.setOnDismissListener(dialog -> { if (!textFinished) finishText(false); });
            textDialog.getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE | WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE);
            textDialog.show();
            textDialog.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(0xffedf4f4);
            textDialog.getButton(AlertDialog.BUTTON_NEGATIVE).setTextColor(0xffedf4f4);
            textDialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> finishText(true));
            textField.requestFocus();
            textField.selectAll();
            textField.post(() -> {
                if (textField != null && textDialog != null && textDialog.isShowing()) {
                    ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showSoftInput(textField, InputMethodManager.SHOW_IMPLICIT);
                }
            });
        });
    }

    private void finishText(boolean accept) {
        finishText(accept, true);
    }

    private void finishText(boolean accept, boolean validate) {
        if (textFinished) return;
        String value = textField == null ? "" : textField.getText().toString();
        if (accept && validate && value.getBytes(StandardCharsets.UTF_8).length > textLimit) {
            textField.setError("Text is too long (maximum " + textLimit + " UTF-8 bytes)");
            return;
        }
        textFinished = true;
        android.util.Log.d("wf_property_text", "field=" + textId + " accepted=" + accept
                + " bytes=" + value.getBytes(StandardCharsets.UTF_8).length);
        textResult(textSession, textId, value.getBytes(StandardCharsets.UTF_8), accept);
        dismissPropertyTextNow();
    }

    private void dismissPropertyTextNow() {
        textFinished = true;
        if (textField != null) ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(textField.getWindowToken(), 0);
        AlertDialog old = textDialog;
        textDialog = null;
        textField = null;
        if (old != null) old.dismiss();
    }

    public void dismissPropertyText(long session) {
        runOnUiThread(() -> { if (textSession == session) dismissPropertyTextNow(); });
    }

    @Override protected void onStop() { finishText(false); super.onStop(); }
    @Override protected void onDestroy() { dismissPropertyTextNow(); super.onDestroy(); }
}

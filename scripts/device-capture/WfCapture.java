import android.app.UiAutomation;
import android.graphics.Bitmap;
import android.os.HandlerThread;
import java.io.FileOutputStream;

/** Observational shell helper: no input, app launch or display/settings changes. */
public final class WfCapture {
    public static void main(String[] args) throws Exception {
        if (args.length != 1 || !args[0].matches("/data/local/tmp/wf-J-[a-f0-9]+-automation.png"))
            throw new IllegalArgumentException("Expected coordinator-owned output path");
        HandlerThread thread = new HandlerThread("wf-capture");
        thread.start();
        UiAutomation automation = null;
        boolean connected = false;
        try {
            Class<?> connectionType = Class.forName("android.app.IUiAutomationConnection");
            Object connection = Class.forName("android.app.UiAutomationConnection")
                .getDeclaredConstructor().newInstance();
            automation = (UiAutomation) UiAutomation.class
                .getDeclaredConstructor(android.os.Looper.class, connectionType)
                .newInstance(thread.getLooper(), connection);
            // Preserve existing accessibility services; this helper needs no accessibility.
            UiAutomation.class.getMethod("connect", int.class).invoke(automation, 3);
            connected = true;
            Bitmap image = automation.takeScreenshot();
            if (image == null) throw new IllegalStateException("UI Automation returned no bitmap");
            try (FileOutputStream output = new FileOutputStream(args[0])) {
                if (!image.compress(Bitmap.CompressFormat.PNG, 100, output))
                    throw new IllegalStateException("PNG compression failed");
            }
            image.recycle();
        } finally {
            if (connected) UiAutomation.class.getMethod("disconnect").invoke(automation);
            thread.quitSafely();
        }
        System.exit(0);
    }
}

package org.worldfoundry.screensaver;

/** Selects a native TV buffer; zero dimensions mean use the view's layout size. */
final class SurfaceResolution {
    private SurfaceResolution() {}

    static int[] choose(boolean tv, int viewWidth, int viewHeight, int logicalWidth,
                        int logicalHeight, int physicalWidth, int physicalHeight) {
        if (!tv || viewWidth <= 0 || viewHeight <= 0 || logicalWidth <= 0 || logicalHeight <= 0
                || physicalWidth <= 0 || physicalHeight <= 0) return new int[] {0, 0};
        if ((logicalWidth < logicalHeight) != (physicalWidth < physicalHeight)) {
            int swap = physicalWidth; physicalWidth = physicalHeight; physicalHeight = swap;
        }
        if (viewWidth == logicalWidth && viewHeight == logicalHeight
                && physicalWidth >= 3840 && physicalHeight >= 2160
                && (long) physicalWidth * logicalHeight == (long) physicalHeight * logicalWidth) {
            return new int[] {physicalWidth, physicalHeight};
        }
        return new int[] {0, 0};
    }
}

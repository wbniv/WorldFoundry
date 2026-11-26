package org.worldfoundry.screensaver;

import java.util.Arrays;

public final class SurfaceResolutionTest {
    private static void expect(int[] expected, int[] actual) {
        if (!Arrays.equals(expected, actual)) throw new AssertionError(Arrays.toString(actual));
    }
    public static void main(String[] args) {
        int[] layout = {0, 0};
        expect(new int[] {3840, 2160}, SurfaceResolution.choose(true, 1920, 1080, 1920, 1080, 3840, 2160));
        expect(layout, SurfaceResolution.choose(true, 1920, 1080, 1920, 1080, 1920, 1080));
        expect(layout, SurfaceResolution.choose(false, 1920, 1080, 1920, 1080, 3840, 2160));
        expect(layout, SurfaceResolution.choose(true, 1280, 720, 1920, 1080, 3840, 2160));
        expect(layout, SurfaceResolution.choose(true, 0, 0, 0, 0, 0, 0));
        expect(layout, SurfaceResolution.choose(true, 1920, 1080, 1920, 1080, 4096, 2160));
        expect(layout, SurfaceResolution.choose(true, 1080, 1920, 1080, 1920, 3840, 2160));
        expect(new int[] {3840, 2160}, SurfaceResolution.choose(true, 1920, 1080, 1920, 1080, 2160, 3840));
        System.out.println("SurfaceResolution: 8 checks passed");
    }
}

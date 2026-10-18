package org.worldfoundry.screensaver;

import android.content.Context;
import android.content.SharedPreferences;

import java.security.SecureRandom;

/** The content choice shared by the TV app, Dream, and coordinator settings call. */
final class TankChoice {
    static final String RANDOM = "random";
    static final String[] IDS = {
            "aquarium", "aquarium_blue_shrimp", "aquarium_betta", "aquarium_jellyfish",
            "aquarium_lionfish", "aquarium_plants", "aquarium_arowana",
            "aquarium_tiger_barbs"
    };
    static final String[] LABELS = {
            "Clownfish", "Blue Shrimp", "Betta", "Jellyfish", "Lionfish",
            "Planted Urchin", "Arowana", "Tiger Barbs"
    };

    private static final String PREFS = "screensaver";
    private static final String KEY = "tank";
    private static final SecureRandom RNG = new SecureRandom();

    private TankChoice() { }

    static boolean valid(String id) {
        if (RANDOM.equals(id)) return true;
        for (String candidate : IDS) {
            if (candidate.equals(id)) return true;
        }
        return false;
    }

    static int indexOf(String id) {
        for (int i = 0; i < IDS.length; i++) {
            if (IDS[i].equals(id)) return i;
        }
        return 0;
    }

    static String get(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String id = prefs.getString(KEY, RANDOM);
        return valid(id) ? id : RANDOM;
    }

    static boolean set(Context context, String id) {
        if (!valid(id)) return false;
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString(KEY, id).commit();
    }

    /** Resolve Random once when the Dream starts, never on each frame. */
    static String chooseForDream(Context context) {
        String id = get(context);
        return RANDOM.equals(id) ? IDS[RNG.nextInt(IDS.length)] : id;
    }
}

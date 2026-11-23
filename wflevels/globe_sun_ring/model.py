"""Time and geometry for the civil-time-calibrated 24-hour globe."""
import math

HOME_LATITUDE = 13.7563
HOME_LONGITUDE = 100.5018

# Representatives for every UTC offset in the system IANA database in 2026,
# including seasonal offsets and 30/45-minute zones. An offset can represent
# many zones: this is a guess, not the device's reported physical location.
# Values are (label, latitude, longitude), east positive.
HOME_BY_OFFSET = {
    -720: ('Baker Island (uninhabited)', .19, -176.48),
    -660: ('Pago Pago', -14.28, -170.70), -600: ('Honolulu', 21.31, -157.86),
    -570: ('Taiohae', -8.91, -140.10), -540: ('Anchorage', 61.22, -149.90),
    -480: ('Los Angeles', 34.05, -118.24), -420: ('Denver', 39.74, -104.99),
    -360: ('Chicago', 41.88, -87.63), -300: ('New York', 40.71, -74.01),
    -240: ('Santo Domingo', 18.49, -69.93), -210: ("St John's", 47.56, -52.71),
    -180: ('Buenos Aires', -34.60, -58.38), -150: ("St John's (daylight)", 47.56, -52.71),
    -120: ('Fernando de Noronha', -3.85, -32.42), -60: ('Praia', 14.92, -23.51),
    0: ('London', 51.51, -.13), 60: ('Paris', 48.86, 2.35),
    120: ('Cairo', 30.04, 31.24), 180: ('Istanbul', 41.01, 28.98),
    210: ('Tehran', 35.69, 51.39), 240: ('Dubai', 25.20, 55.27),
    270: ('Kabul', 34.56, 69.21), 300: ('Karachi', 24.86, 67.01),
    330: ('Delhi', 28.61, 77.21), 345: ('Kathmandu', 27.72, 85.32),
    360: ('Dhaka', 23.81, 90.41), 390: ('Yangon', 16.87, 96.20),
    420: ('Bangkok', 13.7563, 100.5018), 480: ('Singapore', 1.35, 103.82),
    525: ('Eucla', -31.68, 128.88), 540: ('Tokyo', 35.68, 139.69),
    570: ('Darwin', -12.46, 130.84), 600: ('Brisbane', -27.47, 153.03),
    630: ('Lord Howe Island (daylight)', -31.55, 159.08), 660: ('Sydney (daylight)', -33.87, 151.21),
    720: ('Auckland', -36.85, 174.76), 765: ('Chatham Islands', -43.95, -176.56),
    780: ('Auckland (daylight)', -36.85, 174.76),
    825: ('Chatham Islands (daylight)', -43.95, -176.56),
    840: ('Kiritimati', 1.87, -157.43),
}


def home_for_offset(offset_minutes):
    """Choose the closest known offset; unusual offsets still get a pin."""
    nearest = min(HOME_BY_OFFSET, key=lambda key: (abs(key-offset_minutes), key))
    return HOME_BY_OFFSET[nearest]


def civil_hours(hour, minute, second=0.0):
    return (hour + minute / 60.0 + second / 3600.0) % 24.0


def globe_turn(hour, minute, second=0.0, longitude=HOME_LONGITUDE):
    """World rotation in turns: home meridian meets the device civil-time tick."""
    return ((civil_hours(hour, minute, second) - 12.0) / 24.0 - longitude / 360.0) % 1.0


def ring_hour(longitude, turn):
    """Dial time for a longitude, interpreted as civil-calibrated solar time."""
    return (12.0 + 24.0 * (turn + longitude / 360.0)) % 24.0


def sunward(longitude, turn):
    """Cosine of the angle from the sunward meridian (positive by day)."""
    return math.cos(math.tau * (turn + longitude / 360.0))


def city_lit(longitude, turn):
    return sunward(longitude, turn) < 0.0

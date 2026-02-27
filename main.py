import functions_framework
from skyfield.api import Topos, load
from datetime import datetime, timedelta
import pytz

# Helper to convert degrees to compass directions
def get_compass_dir(degrees):
    dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    ix = round(degrees / (360. / len(dirs)))
    return dirs[ix % len(dirs)]

@functions_framework.http
def check_satellite_pass(request):
    # 1. HANDLE CORS (Browser Security)
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
        }
        return ('', 204, headers)

    headers = {'Access-Control-Allow-Origin': '*'}

    # 2. GET USER LOCATION DATA
    request_json = request.get_json(silent=True)
    if not request_json or 'latitude' not in request_json:
        return ("Error: Location data missing.", 400, headers)
    
    lat, lon = request_json['latitude'], request_json['longitude']

    # 3. SETUP SATELLITE & PLANETARY DATA
    ts = load.timescale()
    # TLE for ISS
    satellites = load.tle_file('https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle')
    iss = {sat.name: sat for sat in satellites}['ISS (ZARYA)']
    # Ephemeris for Sun/Earth positions (needed for visibility check)
    eph = load('de421.bsp') 
    
    user_pos = Topos(f'{lat} N', f'{lon} E')

    # 4. CALCULATE PASSES (Next 24 Hours)
    t0 = ts.now()
    t1 = ts.from_datetime(datetime.now(pytz.utc) + timedelta(hours=24))
    times, events = iss.find_events(user_pos, t0, t1, altitude_degrees=30.0)

    # 5. PROCESS & LABEL PASSES
    results = []
    ist = pytz.timezone('Asia/Kolkata')

    for ti, event in zip(times, events):
        if event == 1:  # Peak of the pass
            # Calculate Position
            difference = iss - user_pos
            topocentric = difference.at(ti)
            alt, az, distance = topocentric.altaz()
            
            # Visibility Math:
            # Check if ISS is hit by Sun
            is_sunlit = iss.at(ti).is_sunlit(eph)
            # Check if Sun is below horizon for the user (Darkness)
            sun_alt = (eph['earth'] + user_pos).at(ti).observe(eph['sun']).apparent().altaz()[0]
            is_dark_ground = sun_alt.degrees < -6

            local_time = ti.astimezone(ist)
            
            # Classification
            if is_sunlit and is_dark_ground:
                label = "🌟 VISIBLE PASS (Naked Eye)"
            else:
                label = "📡 RADIO PASS (Telemetry Only)"

            results.append(
                f"{label}\n"
                f"⏰ {local_time.strftime('%I:%M:%S %p')}\n"
                f"🔭 Alt: {alt.degrees:.1f}° | 🧭 Dir: {get_compass_dir(az.degrees)} ({az.degrees:.0f}°)\n"
                f"--------------------------------"
            )

    if not results:
        return ("No passes detected in the next 24 hours.", 200, headers)
    
    final_output = "🛰️ ORBITAL ALERT: ISS PREDICTIONS\n\n" + "\n".join(results)
    return (final_output, 200, headers)
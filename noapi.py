from flask import Flask, request, jsonify, render_template
import requests
import openai   # If you want Gemini, replace this with google.generativeai
from datetime import datetime, timedelta

app = Flask(__name__)

# -------------------------------
# API KEYS (replace with real keys)
# -------------------------------

OPENWEATHER_KEY = ""
GOOGLE_MAPS_KEY = ""
AMADEUS_KEY = ""
OPENAI_KEY = ""
AMADEUS_CLIENT_ID = ""
AMADEUS_CLIENT_SECRET = ""

openai.api_key = OPENAI_KEY


# -------------------------------
# WEATHER API
# -------------------------------
def get_weather(destination):
    print("Fetching weather data...")
    url = f"https://api.openweathermap.org/data/2.5/weather?q={destination}&appid={OPENWEATHER_KEY}&units=metric"
    print("Weather API URL:", url)
    res = requests.get(url).json()
    print("Weather data received:", res)
    temp = res.get('main', {}).get('temp', "N/A")
    desc = res.get('weather', [{}])[0].get('description', "N/A")
    return f"{temp}°C, {desc}"


# -------------------------------
# AMADEUS: GET TOKEN
# -------------------------------
def get_amadeus_token():
    token_url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_CLIENT_ID,
        "client_secret": AMADEUS_CLIENT_SECRET
    }
    res = requests.post(token_url, headers=headers, data=data).json()
    return res.get("access_token")


# -------------------------------
# AMADEUS: GET IATA CODE
# -------------------------------
def get_iata_code(city):
    token = get_amadeus_token()
    url = "https://test.api.amadeus.com/v1/reference-data/locations"
    params = {"keyword": city, "subType": "CITY"}
    res = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params).json()
    print("IATA code response:", res)
    try:
        return res["data"][0]["iataCode"]
    except:
        return None


# -------------------------------
# AMADEUS: FLIGHT SEARCH
# -------------------------------
def get_flight(destination):
    token = get_amadeus_token()
    origin = "DEL"   # Default origin Delhi (you can change this)
    iata_mapping = {
    "Dehradun": "DED",
    "Delhi": "DEL",
    "Mumbai": "BOM",
    "Bangalore": "BLR",
    "Kolkata": "CCU"
    }
    # dest_code = get_iata_code(destination)
    dest_code = iata_mapping.get(destination, None)
    departure_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    if not dest_code:
        return "No airport found for this city"

    flight_url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": dest_code,
        "adults": 1,
        "currencyCode": "INR",
        "departureDate": departure_date,
        "max": 1
    }
    print("Flighturl:", flight_url)
    res = requests.get(flight_url, headers={"Authorization": f"Bearer {token}"}, params=params).json()
    print("Flight data received:", res)
    try:
        price = res["data"][0]["price"]["total"]
        airline = res["data"][0]["validatingAirlineCodes"][0]
        return f"Cheapest flight ~₹{price} via {airline}"
    except:
        return "No flight data available"
    
# -------------------------------
# Wiki Api: PLACES
# -------------------------------
def get_places_wiki(city):
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts",
        "titles": f"Tourist attractions in {city}",
        "exintro": True,
        "redirects": 1
    }
    headers = {"User-Agent": "MyTravelPlanner/1.0 (student project)"}

    try:
        res = requests.get(url, params=params, headers=headers)
        res.raise_for_status()  # raises error if status != 200
        data = res.json()
    except Exception as e:
        print("Wikipedia API error:", e)
        return ["No attractions found"]
    print("Wikipedia data received:", data)
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        text = page.get("extract", "")
        attractions = [t.strip() for t in text.split('.') if len(t.strip())>5][:5]
        return attractions
    return ["No attractions found"]

# -------------------------------
# GOOGLE MAPS: PLACES
# -------------------------------
def get_places(destination):
    url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query=tourist+attractions+in+{destination}&key={GOOGLE_MAPS_KEY}"
    res = requests.get(url).json()
    print("Places data received:", res)
    places = []
    for p in res.get("results", [])[:3]:
        places.append(p.get("name"))
    return places if places else ["No attractions found"]


# -------------------------------
# AI ITINERARY (OpenAI)
# -------------------------------
def get_ai_plan(destination, day, weather, attractions):
    prompt = f"""
    You are a travel planner. Create a short itinerary for Day {day} in {destination}.
    Weather: {weather}.
    Must include these attractions if possible: {', '.join(attractions)}.
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("OpenAI API error, using fallback plan. exception is", e)
        return f"Explore {destination} on Day {day}. Suggested spots: {', '.join(attractions)}"


# -------------------------------
# ROUTES
# -------------------------------
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/get_itinerary', methods=['POST'])
def get_itinerary():
    data = request.json
    destination = data.get("destination")
    days = int(data.get("days"))

    weather_info = get_weather(destination)
    print("Weather information:", weather_info)
    flight_info = get_flight(destination)
    print("Flight information:", flight_info)
    attractions = get_places_wiki(destination)
    print("Attractions found:", attractions)
    itinerary = []
    for i in range(1, days + 1):
        plan = get_ai_plan(destination, i, weather_info, attractions)
        print(f"Day {i} plan:", plan)
        itinerary.append({
            "day": i,
            "plan": plan,
            "weather": weather_info,
            "flights": flight_info,
            "attractions": attractions
        })

    return jsonify(itinerary)


if __name__ == "__main__":
    print("🚀 File started, launching Flask...")
    app.run(debug=True, port=5000)


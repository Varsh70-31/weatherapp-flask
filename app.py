from flask import Flask, render_template, request, jsonify
import requests
import os
from datetime import datetime
import json

app = Flask(__name__)

# OpenWeatherMap API configuration
# Get your free API key from: https://openweathermap.org/api
API_KEY = os.environ.get('OPENWEATHER_API_KEY', 'your_actual_api_key_here')
BASE_URL = 'https://api.openweathermap.org'

def get_weather_data(city):
    """Fetch current weather and forecast data for a city"""
    try:
        # Current weather
        current_url = f"{BASE_URL}/weather?q={city}&appid={API_KEY}&units=metric"
        current_response = requests.get(current_url, timeout=10)
        current_response.raise_for_status()
        current_data = current_response.json()
        
        # 5-day forecast
        forecast_url = f"{BASE_URL}/forecast?q={city}&appid={API_KEY}&units=metric"
        forecast_response = requests.get(forecast_url, timeout=10)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()
        
        # Process current weather
        weather_info = {
            'city': current_data['name'],
            'country': current_data['sys']['country'],
            'temperature': round(current_data['main']['temp']),
            'feels_like': round(current_data['main']['feels_like']),
            'humidity': current_data['main']['humidity'],
            'pressure': current_data['main']['pressure'],
            'visibility': current_data.get('visibility', 0) / 1000,  # Convert to km
            'wind_speed': current_data['wind']['speed'],
            'wind_direction': current_data['wind'].get('deg', 0),
            'description': current_data['weather'][0]['description'].title(),
            'icon': current_data['weather'][0]['icon'],
            'sunrise': datetime.fromtimestamp(current_data['sys']['sunrise']).strftime('%H:%M'),
            'sunset': datetime.fromtimestamp(current_data['sys']['sunset']).strftime('%H:%M'),
            'timezone': current_data['timezone']
        }
        
        # Process 5-day forecast (take one reading per day at 12:00 or closest time)
        daily_forecast = []
        processed_dates = set()
        
        # Debug: Print first few items to see the structure
        print("DEBUG: Forecast data structure:")
        for i, item in enumerate(forecast_data['list'][:3]):
            dt = datetime.fromtimestamp(item['dt'])
            print(f"  Item {i}: {dt.strftime('%Y-%m-%d %H:%M')} - {item['weather'][0]['description']}")
        
        # Group by date and find the best time for each day
        daily_data = {}
        for item in forecast_data['list']:
            dt = datetime.fromtimestamp(item['dt'])
            date = dt.date()
            time = dt.strftime('%H:%M')
            
            # Store all times for each date
            if date not in daily_data:
                daily_data[date] = []
            daily_data[date].append({
                'time': time,
                'datetime': dt,
                'data': item
            })
        
        # Pick the best time for each day (prefer 12:00, then 15:00, then 09:00, then first available)
        preferred_times = ['12:00', '15:00', '09:00', '18:00', '06:00']
        
        for date in sorted(daily_data.keys())[:5]:  # Only take first 5 days
            day_items = daily_data[date]
            
            # Find the best time for this day
            selected_item = None
            for preferred_time in preferred_times:
                for item in day_items:
                    if item['time'] == preferred_time:
                        selected_item = item
                        break
                if selected_item:
                    break
            
            # If no preferred time found, take the first item of the day
            if not selected_item and day_items:
                selected_item = day_items[0]
            
            if selected_item:
                data = selected_item['data']
                daily_forecast.append({
                    'date': date.strftime('%a, %b %d'),
                    'temperature': round(data['main']['temp']),
                    'temp_min': round(data['main']['temp_min']),
                    'temp_max': round(data['main']['temp_max']),
                    'description': data['weather'][0]['description'].title(),
                    'icon': data['weather'][0]['icon'],
                    'humidity': data['main']['humidity'],
                    'time': selected_item['time']
                })
        
        print(f"DEBUG: Processed {len(daily_forecast)} forecast days")
        
        weather_info['forecast'] = daily_forecast
        return weather_info
        
    except requests.exceptions.RequestException as e:
        return {'error': f'Network error: {str(e)}'}
    except KeyError as e:
        return {'error': f'Invalid city name or API response: {str(e)}'}
    except Exception as e:
        return {'error': f'Unexpected error: {str(e)}'}

def get_weather_by_coords(lat, lon):
    """Fetch weather data using coordinates"""
    try:
        current_url = f"{BASE_URL}/weather?lat={lat}&lon={lon}&appid={API_KEY}&units=metric"
        current_response = requests.get(current_url, timeout=10)
        current_response.raise_for_status()
        current_data = current_response.json()
        
        city = current_data['name']
        return get_weather_data(city)
        
    except Exception as e:
        return {'error': f'Location error: {str(e)}'}

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/weather', methods=['POST'])
def get_weather():
    """API endpoint to get weather data"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    if 'city' in data:
        weather_data = get_weather_data(data['city'])
    elif 'lat' in data and 'lon' in data:
        weather_data = get_weather_by_coords(data['lat'], data['lon'])
    else:
        return jsonify({'error': 'City name or coordinates required'}), 400
    
    return jsonify(weather_data)

@app.errorhandler(404)
def not_found(error):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/debug-forecast/<city>')
def debug_forecast(city):
    """Debug endpoint to see raw forecast data"""
    try:
        forecast_url = f"{BASE_URL}/forecast?q={city}&appid={API_KEY}&units=metric"
        response = requests.get(forecast_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Format for easy reading
        formatted_list = []
        for item in data['list'][:10]:  # Show first 10 items
            dt = datetime.fromtimestamp(item['dt'])
            formatted_list.append({
                'datetime': dt.strftime('%Y-%m-%d %H:%M'),
                'temp': item['main']['temp'],
                'description': item['weather'][0]['description'],
                'icon': item['weather'][0]['icon']
            })
        
        return jsonify({
            'city': data['city']['name'],
            'total_items': len(data['list']),
            'first_10_items': formatted_list,
            'raw_data': data
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    """Test endpoint to verify API key"""
    if API_KEY == 'your_api_key_here' or not API_KEY:
        return jsonify({
            'error': 'API key not set',
            'instructions': 'Set OPENWEATHER_API_KEY environment variable'
        }), 400
    
    try:
        # Test with a simple API call
        test_url = f"{BASE_URL}/weather?q=London&appid={API_KEY}&units=metric"
        response = requests.get(test_url, timeout=10)
        
        return jsonify({
            'status': 'success' if response.status_code == 200 else 'error',
            'status_code': response.status_code,
            'api_key_length': len(API_KEY),
            'api_key_preview': f"{API_KEY[:8]}...{API_KEY[-4:]}",
            'response': response.json() if response.status_code == 200 else response.text
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Check if API key is set
    if API_KEY == 'your_api_key_here' or not API_KEY:
        print("🔑 API Key Status: NOT SET")
        print("📋 Steps to fix:")
        print("   1. Go to https://openweathermap.org/api")
        print("   2. Sign up for free account")
        print("   3. Get your API key")
        print("   4. Set environment variable:")
        print("      export OPENWEATHER_API_KEY='your_actual_key'")
        print("   5. Wait 10-60 minutes for activation")
    else:
        print(f"🔑 API Key Status: SET ({len(API_KEY)} characters)")
        print(f"🔍 Key Preview: {API_KEY[:8]}...{API_KEY[-4:]}")
        print("📝 Test your API key at: http://localhost:5000/test-api")
    
    print("🌐 Starting server at: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)

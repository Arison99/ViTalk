from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
import requests
from datetime import datetime, timedelta
import re
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Create blueprint
satellite_bp = Blueprint('satellite', __name__, url_prefix='/satellites')

# Base API URL - Fixed to match documentation
TLE_API_BASE = "https://tle.ivanstanojevic.me/api/tle"

def create_robust_session():
    """Create a requests session with retry strategy and proper headers"""
    session = requests.Session()
    
    # Define retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    
    # Mount adapter with retry strategy
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Set headers to mimic a real browser
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache'
    })
    
    return session

def make_api_request(url, params=None, timeout=15, max_retries=2):
    """Make API request with robust error handling and retries"""
    session = create_robust_session()
    
    for attempt in range(max_retries + 1):
        try:
            print(f"API Request attempt {attempt + 1}: {url}")
            if params:
                print(f"Parameters: {params}")
            
            response = session.get(url, params=params, timeout=timeout)
            
            # Check if we got a valid response
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"API Success: Got {len(str(data))} characters of data")
                    return data, None
                except ValueError as e:
                    print(f"JSON parsing error: {e}")
                    return None, "Invalid JSON response from API"
            else:
                print(f"HTTP Error: {response.status_code}")
                if response.status_code == 404:
                    return None, "Resource not found"
                elif response.status_code >= 500:
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                return None, f"API returned status code {response.status_code}"
                
        except requests.exceptions.Timeout:
            print(f"Timeout on attempt {attempt + 1}")
            if attempt < max_retries:
                time.sleep(1)
                continue
            return None, "Request timeout after multiple attempts"
            
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error on attempt {attempt + 1}: {e}")
            if attempt < max_retries:
                time.sleep(2)
                continue
            return None, "Connection failed after multiple attempts"
            
        except Exception as e:
            print(f"Unexpected error on attempt {attempt + 1}: {e}")
            if attempt < max_retries:
                time.sleep(1)
                continue
            return None, f"Unexpected error: {str(e)}"
    
    return None, "All retry attempts failed"

def validate_norad_id(norad_id):
    """Validate NORAD catalog ID format"""
    try:
        return int(norad_id) > 0
    except (ValueError, TypeError):
        return False

def parse_tle_data(tle_data):
    """Parse TLE data and extract useful information"""
    if not tle_data:
        return None
    
    try:
        line1 = tle_data.get('line1', '')
        line2 = tle_data.get('line2', '')
        
        # Parse epoch from line 1
        epoch_match = re.search(r'(\d{2})(\d{3}\.\d+)', line1)
        if epoch_match:
            year = int(epoch_match.group(1))
            # Convert 2-digit year to 4-digit (assuming 20xx for years < 57, 19xx for >= 57)
            year = 2000 + year if year < 57 else 1900 + year
            day_of_year = float(epoch_match.group(2))
            
            # Convert day of year to date
            epoch_date = datetime(year, 1, 1) + timedelta(days=day_of_year - 1)
            tle_data['epoch'] = epoch_date.strftime('%Y-%m-%d %H:%M:%S UTC')
        
        # Parse inclination and other orbital parameters from line 2
        line2_parts = line2.split()
        if len(line2_parts) >= 8:
            tle_data['inclination'] = float(line2_parts[2])
            tle_data['eccentricity'] = float('0.' + line2_parts[4])  # Decimal point assumed
            mean_motion = float(line2_parts[7][:11])  # Revolutions per day
            tle_data['orbital_period'] = 1440 / mean_motion if mean_motion > 0 else None  # Minutes
            tle_data['mean_motion'] = mean_motion
            
    except Exception as e:
        print(f"Error parsing TLE data: {e}")
    
    return tle_data

def format_collection_params(params):
    """Format parameters for the TLE API collection endpoint"""
    formatted_params = {}
    
    # Map common search terms
    if 'query' in params:
        formatted_params['search'] = params['query']
    
    # Handle sorting
    if 'sort' in params:
        valid_sorts = ['id', 'name', 'popularity', 'inclination', 'eccentricity', 'period']
        if params['sort'] in valid_sorts:
            formatted_params['sort'] = params['sort']
    
    if 'sort_dir' in params or 'sort-dir' in params:
        direction = params.get('sort_dir', params.get('sort-dir', 'asc'))
        if direction in ['asc', 'desc']:
            formatted_params['sort-dir'] = direction
    
    # Handle pagination
    if 'page' in params:
        try:
            page = int(params['page'])
            if page >= 1:
                formatted_params['page'] = page
        except ValueError:
            pass
    
    if 'page_size' in params or 'page-size' in params:
        try:
            page_size = int(params.get('page_size', params.get('page-size', 20)))
            if 1 <= page_size <= 100:
                formatted_params['page-size'] = page_size
        except ValueError:
            pass
    
    # Handle orbital parameter filters
    orbital_filters = [
        'eccentricity[gte]', 'eccentricity[lte]',
        'inclination[lt]', 'inclination[gt]',
        'period[lt]', 'period[gt]'
    ]
    
    for filter_param in orbital_filters:
        if filter_param in params:
            try:
                value = float(params[filter_param])
                formatted_params[filter_param] = value
            except ValueError:
                pass
    
    return formatted_params

@satellite_bp.route('/')
def index():
    """Main satellite tracker page"""
    return render_template('satellite/index.html')

@satellite_bp.route('/search')
def search_page():
    """Search page for satellites"""
    return render_template('satellite/search.html')

@satellite_bp.route('/api/search')
def api_search():
    """API endpoint for searching satellites - Fixed to use correct TLE API"""
    query = request.args.get('query', '').strip()
    
    # Build parameters for the collection endpoint
    params = {
        'search': query if query else '*',
        'page-size': min(int(request.args.get('limit', 20)), 100),
        'page': max(int(request.args.get('page', 1)), 1)
    }
    
    # Add any additional filters
    for key, value in request.args.items():
        if key in ['sort', 'sort-dir'] or '[' in key:  # Orbital filters
            params[key] = value
    
    # Make API request with robust error handling
    data, error = make_api_request(TLE_API_BASE, params=params)
    
    if error:
        print(f"Search API error: {error}")
        return jsonify({'error': error, 'satellites': [], 'count': 0}), 500
    
    if not data or 'member' not in data:
        return jsonify({'error': 'Invalid API response format', 'satellites': [], 'count': 0}), 500
    
    try:
        satellites = data.get('member', [])
        
        # Parse TLE data for each satellite
        parsed_satellites = []
        for satellite in satellites:
            parsed_satellite = parse_tle_data(satellite)
            if parsed_satellite:
                parsed_satellites.append(parsed_satellite)
        
        return jsonify({
            'satellites': parsed_satellites,
            'count': len(parsed_satellites),
            'total_items': data.get('totalItems', 0),
            'pagination': {
                'current_page': params.get('page', 1),
                'page_size': params.get('page-size', 20),
                'total_items': data.get('totalItems', 0)
            },
            'view': data.get('view', {}),
            'success': True
        })
        
    except Exception as e:
        print(f"Error processing search results: {e}")
        return jsonify({'error': 'Error processing search results', 'satellites': [], 'count': 0}), 500

@satellite_bp.route('/api/satellite/<int:satellite_id>')
def api_get_satellite(satellite_id):
    """API endpoint for getting specific satellite data - Fixed endpoint"""
    if not validate_norad_id(satellite_id):
        return jsonify({'error': 'Invalid satellite ID'}), 400
    
    # Make API request with robust error handling
    url = f"{TLE_API_BASE}/{satellite_id}"
    data, error = make_api_request(url)
    
    if error:
        print(f"Satellite API error for ID {satellite_id}: {error}")
        if "not found" in error.lower():
            return jsonify({'error': 'Satellite not found'}), 404
        return jsonify({'error': error}), 500
    
    if not data:
        return jsonify({'error': 'No data received from API'}), 500
    
    try:
        satellite = parse_tle_data(data)
        
        if not satellite:
            return jsonify({'error': 'Unable to parse satellite data'}), 500
        
        return jsonify({'satellite': satellite, 'success': True})
        
    except Exception as e:
        print(f"Error processing satellite data: {e}")
        return jsonify({'error': 'Error processing satellite data'}), 500

@satellite_bp.route('/satellite/<int:satellite_id>')
def satellite_detail(satellite_id):
    """Satellite detail page - Fixed parameter name"""
    return render_template('satellite/detail.html', satellite_id=satellite_id)

@satellite_bp.route('/api/propagate/<int:satellite_id>')
def api_propagate_satellite(satellite_id):
    """API endpoint for satellite orbital propagation"""
    if not validate_norad_id(satellite_id):
        return jsonify({'error': 'Invalid satellite ID'}), 400
    
    # Get target date from query parameters
    target_date = request.args.get('date')
    if not target_date:
        target_date = datetime.utcnow().isoformat() + '+00:00'
    
    # Make API request with robust error handling
    url = f"{TLE_API_BASE}/{satellite_id}/propagate"
    params = {'date': target_date}
    data, error = make_api_request(url, params=params)
    
    if error:
        print(f"Propagation API error for ID {satellite_id}: {error}")
        if "not found" in error.lower():
            return jsonify({'error': 'Satellite not found'}), 404
        return jsonify({'error': error}), 500
    
    if not data:
        return jsonify({'error': 'No propagation data received'}), 500
    
    return jsonify({'propagation': data, 'success': True})

@satellite_bp.route('/api/advanced-search')
def api_advanced_search():
    """Advanced search with orbital parameter filters"""
    # Format all request parameters for the TLE API
    params = format_collection_params(request.args)
    
    # Default search if none provided
    if 'search' not in params:
        params['search'] = '*'
    
    # Make API request with robust error handling
    data, error = make_api_request(TLE_API_BASE, params=params, timeout=20)
    
    if error:
        print(f"Advanced search API error: {error}")
        return jsonify({'error': error, 'satellites': [], 'count': 0}), 500
    
    if not data or 'member' not in data:
        return jsonify({'error': 'Invalid API response format', 'satellites': [], 'count': 0}), 500
    
    try:
        satellites = data.get('member', [])
        
        # Parse TLE data for each satellite
        parsed_satellites = []
        for satellite in satellites:
            parsed_satellite = parse_tle_data(satellite)
            if parsed_satellite:
                parsed_satellites.append(parsed_satellite)
        
        return jsonify({
            'satellites': parsed_satellites,
            'count': len(parsed_satellites),
            'total_items': data.get('totalItems', 0),
            'parameters': data.get('parameters', {}),
            'view': data.get('view', {}),
            'applied_filters': params,
            'success': True
        })
        
    except Exception as e:
        print(f"Error processing advanced search results: {e}")
        return jsonify({'error': 'Error processing search results', 'satellites': [], 'count': 0}), 500

# Add a test endpoint to check API connectivity
@satellite_bp.route('/api/test')
def api_test():
    """Test API connectivity"""
    try:
        data, error = make_api_request(TLE_API_BASE, params={'search': 'ISS', 'page-size': 1})
        
        if error:
            return jsonify({
                'status': 'error',
                'message': error,
                'api_url': TLE_API_BASE
            })
        
        return jsonify({
            'status': 'success',
            'message': 'API is responding',
            'api_url': TLE_API_BASE,
            'sample_data': bool(data and 'member' in data)
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'api_url': TLE_API_BASE
        })

# Updated popular satellites with correct IDs
POPULAR_SATELLITES = [
    {'satellite_id': 25544, 'name': 'International Space Station', 'category': 'Space Station'},
    {'satellite_id': 20580, 'name': 'Hubble Space Telescope', 'category': 'Observatory'},
    {'satellite_id': 39084, 'name': 'NOAA-19', 'category': 'Weather'},
    {'satellite_id': 33591, 'name': 'NOAA-18', 'category': 'Weather'},
    {'satellite_id': 28654, 'name': 'NOAA-17', 'category': 'Weather'},
    {'satellite_id': 43013, 'name': 'STARLINK-1007', 'category': 'Communication'},
    {'satellite_id': 37849, 'name': 'GOES-16', 'category': 'Weather'},
]

@satellite_bp.route('/popular')
def popular_satellites():
    """Show popular satellites"""
    return render_template('satellite/popular.html', satellites=POPULAR_SATELLITES)

@satellite_bp.route('/advanced-search')
def advanced_search_page():
    """Advanced search page with orbital parameter filters"""
    return render_template('satellite/advanced_search.html')

@satellite_bp.context_processor
def inject_popular_satellites():
    """Make popular satellites available to all templates"""
    return dict(popular_satellites=POPULAR_SATELLITES)

# Error handlers
@satellite_bp.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@satellite_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500
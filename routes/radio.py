from flask import Blueprint, render_template, request, jsonify
import requests
import logging
import random
from urllib.parse import urljoin

# Create blueprint
radio_bp = Blueprint('radio', __name__, url_prefix='/radio')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Radio Browser API base URLs - we'll use multiple servers for redundancy
API_SERVERS = [
    "https://de1.api.radio-browser.info",
    "https://nl1.api.radio-browser.info", 
    "https://fi1.api.radio-browser.info"
]

# Cache for streaming servers
_streaming_servers = None
_servers_cache_time = None

def get_active_streaming_servers():
    """Get list of active streaming servers with caching"""
    global _streaming_servers, _servers_cache_time
    import time
    
    current_time = time.time()
    # Cache for 5 minutes
    if _streaming_servers and _servers_cache_time and (current_time - _servers_cache_time) < 300:
        return _streaming_servers
    
    # Try to get streaming servers
    for base_url in API_SERVERS:
        try:
            url = f"{base_url}/json/streamingservers"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            servers = response.json()
            
            # Filter out servers with errors
            active_servers = [s for s in servers if not s.get('error') and s.get('url')]
            
            if active_servers:
                _streaming_servers = active_servers
                _servers_cache_time = current_time
                logger.info(f"Found {len(active_servers)} active streaming servers")
                return active_servers
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to get streaming servers from {base_url}: {e}")
            continue
    
    # Fallback to default servers if API fails
    logger.warning("Using fallback streaming servers")
    _streaming_servers = API_SERVERS
    _servers_cache_time = current_time
    return _streaming_servers

def make_api_request(endpoint, params=None, use_streaming_server=False):
    """Make a request to the Radio Browser API with error handling and server rotation"""
    
    if use_streaming_server:
        # Use streaming servers for station-specific requests
        servers = get_active_streaming_servers()
        # Randomly select a server to distribute load
        selected_servers = random.sample(servers, min(3, len(servers)))
    else:
        # Use main API servers for general requests
        selected_servers = API_SERVERS.copy()
        random.shuffle(selected_servers)
    
    for server in selected_servers:
        try:
            if use_streaming_server and isinstance(server, dict):
                base_url = server['url'].rstrip('/')
            else:
                base_url = server
                
            url = f"{base_url}{endpoint}"
            
            # Add required headers for Radio Browser API
            headers = {
                'User-Agent': 'Flask-Radio-App/1.0',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, params=params, timeout=10, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            if result:  # Only return if we got actual data
                return result
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"API request failed for {server}: {e}")
            continue
        except ValueError as e:  # JSON decode error
            logger.warning(f"Invalid JSON response from {server}: {e}")
            continue
    
    logger.error(f"All servers failed for endpoint: {endpoint}")
    return None

@radio_bp.route('/')
def index():
    """Main radio browser page"""
    return render_template('radio/index.html')

@radio_bp.route('/search')
def search():
    """Search for radio stations"""
    query = request.args.get('q', '').strip()
    country = request.args.get('country', '').strip()
    tag = request.args.get('tag', '').strip()
    
    if not any([query, country, tag]):
        return render_template('radio/search.html', stations=[], query='')
    
    # Build search parameters
    params = {}
    if query:
        params['name'] = query
    if country:
        params['country'] = country
    if tag:
        params['tag'] = tag
    
    # Limit results to prevent overwhelming the UI
    params['limit'] = 50
    params['hidebroken'] = 'true'  # Hide broken stations
    
    stations = make_api_request('/json/stations/search', params)
    
    if stations is None:
        stations = []
        error_message = "Failed to fetch radio stations. Please try again."
    else:
        error_message = None
        # Filter out stations without valid URLs and add additional validation
        valid_stations = []
        for station in stations:
            if (station.get('url_resolved') and 
                station.get('lastcheckok') == 1 and  # Station was working in last check
                not station.get('url_resolved', '').strip() == ''):
                valid_stations.append(station)
        stations = valid_stations
    
    return render_template('radio/search.html', 
                         stations=stations, 
                         query=query,
                         country=country,
                         tag=tag,
                         error=error_message)

@radio_bp.route('/api/countries')
def api_countries():
    """API endpoint to get list of countries"""
    countries = make_api_request('/json/countries')
    if countries:
        # Sort by country name and limit to countries with stations
        countries = sorted([c for c in countries if c.get('stationcount', 0) > 0], 
                          key=lambda x: x.get('name', ''))
    return jsonify(countries or [])

@radio_bp.route('/api/tags')
def api_tags():
    """API endpoint to get popular tags"""
    tags = make_api_request('/json/tags')
    if tags:
        # Limit to top 50 tags and sort by usage
        tags = sorted(tags, key=lambda x: x.get('stationcount', 0), reverse=True)[:50]
    return jsonify(tags or [])

@radio_bp.route('/station/<station_id>')
def station_detail(station_id):
    """Get detailed information about a specific station"""
    # Try to get station by UUID first, then by ID
    station = make_api_request(f'/json/stations/byuuid/{station_id}')
    
    if not station:
        # Try by station ID if UUID fails
        station = make_api_request(f'/json/stations/{station_id}')
    
    if not station or not isinstance(station, list) or len(station) == 0:
        return render_template('radio/error.html', 
                             message="Station not found"), 404
    
    station_data = station[0]
    return render_template('radio/station.html', station=station_data)

@radio_bp.route('/api/play/<station_uuid>')
def api_play_station(station_uuid):
    """API endpoint to get station play URL and increment click counter"""
    
    # First try to get the station info to validate it exists
    station_info = make_api_request(f'/json/stations/byuuid/{station_uuid}')
    
    if not station_info or len(station_info) == 0:
        return jsonify({
            'success': False,
            'message': 'Station not found'
        }), 404
    
    station = station_info[0]
    
    # Try to get the click URL using streaming servers
    click_result = make_api_request(f'/json/url/{station_uuid}', use_streaming_server=True)
    
    # Determine the best URL to use
    play_url = None
    
    if click_result and click_result.get('ok') == 'true':
        # Use the URL from click endpoint (this increments the counter)
        play_url = click_result.get('url')
        logger.info(f"Got click URL for station {station_uuid}: {play_url}")
    
    # Fallback to station's resolved URL
    if not play_url:
        play_url = station.get('url_resolved')
        logger.info(f"Using fallback URL for station {station_uuid}: {play_url}")
    
    # Final fallback to original URL
    if not play_url:
        play_url = station.get('url')
        logger.info(f"Using original URL for station {station_uuid}: {play_url}")
    
    if play_url:
        return jsonify({
            'success': True,
            'url': play_url,
            'name': station.get('name', 'Unknown Station'),
            'homepage': station.get('homepage'),
            'favicon': station.get('favicon'),
            'bitrate': station.get('bitrate'),
            'codec': station.get('codec'),
            'message': 'Station URL retrieved successfully'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'No playable URL found for this station'
        }), 404

@radio_bp.route('/api/streaming-servers')
def api_streaming_servers():
    """API endpoint to get current streaming servers status"""
    servers = get_active_streaming_servers()
    return jsonify({
        'servers': servers,
        'count': len(servers)
    })

@radio_bp.route('/api/check-station/<station_uuid>')
def api_check_station(station_uuid):
    """API endpoint to check if a station is currently working"""
    # Get station info
    station_info = make_api_request(f'/json/stations/byuuid/{station_uuid}')
    
    if not station_info or len(station_info) == 0:
        return jsonify({
            'success': False,
            'message': 'Station not found'
        }), 404
    
    station = station_info[0]
    
    # Check various indicators of station health
    is_working = (
        station.get('lastcheckok') == 1 and
        station.get('url_resolved') and
        station.get('url_resolved').strip() != ''
    )
    
    return jsonify({
        'success': True,
        'working': is_working,
        'last_check_ok': station.get('lastcheckok'),
        'last_check_time': station.get('lastchecktime'),
        'url_resolved': station.get('url_resolved'),
        'codec': station.get('codec'),
        'bitrate': station.get('bitrate')
    })

@radio_bp.route('/favorites')
def favorites():
    """Show user's favorite stations (placeholder for future implementation)"""
    # This would typically integrate with user authentication
    # For now, just show an empty favorites page
    return render_template('radio/favorites.html', stations=[])

# Error handlers for the blueprint
@radio_bp.errorhandler(404)
def not_found(error):
    return render_template('radio/error.html', 
                         message="Page not found"), 404

@radio_bp.errorhandler(500)
def internal_error(error):
    return render_template('radio/error.html', 
                         message="Internal server error"), 500
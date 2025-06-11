from flask import Blueprint, render_template, request
import requests

tvmaze_bp = Blueprint('tvmaze', __name__, template_folder='../templates/tvmaze')

@tvmaze_bp.route('/', methods=['GET'])
def search():
    query = request.args.get('q')
    shows = []
    if query:
        res = requests.get(f'https://api.tvmaze.com/search/shows?q={query}')
        if res.ok:
            shows = res.json()
    if request.headers.get('HX-Request'):
        return render_template('tvmaze/_show_cards.html', shows=shows)
    return render_template('tvmaze/search.html', shows=shows, query=query)

@tvmaze_bp.route('/show/<int:show_id>', methods=['GET'])
def show_detail(show_id):
    page = request.args.get('page', 1, type=int)
    res = requests.get(
        f'https://api.tvmaze.com/shows/{show_id}?embed=episodes'
    )
    if not res.ok:
        return f"Show {show_id} not found", 404
    show = res.json()
    episodes = show['_embedded']['episodes']
    per_page = 10
    start = (page - 1)*per_page
    chunk = episodes[start:start + per_page]
    has_more = start + per_page < len(episodes)

    context = dict(show=show, episodes=chunk, page=page, has_more=has_more)
    if request.headers.get('HX-Request'):
        return render_template('tvmaze/_episode_list.html', **context)
    return render_template('tvmaze/show_detail.html', **context)

@tvmaze_bp.route('/episode/<int:episode_id>', methods=['GET'])
def episode_detail(episode_id):
    res = requests.get(f'https://api.tvmaze.com/episodes/{episode_id}?embed=show')
    if not res.ok:
        return f"Episode {episode_id} not found", 404
    ep = res.json()
    return render_template('tvmaze/episode_detail.html', episode=ep)

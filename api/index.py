"""
EdQuest Web Server - Vercel Serverless Handler
Flask backend for the Twine Generator web interface.
"""

import os
import sys

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import json
import requests
from flask import Flask, request, jsonify, Response

# Try to import twine_generator, with fallback
IMPORT_ERROR = None
try:
    from twine_generator import EducationalContent, generate_educational_scenario, ANTHROPIC_AVAILABLE
    GENERATOR_AVAILABLE = True
except ImportError as e:
    GENERATOR_AVAILABLE = False
    ANTHROPIC_AVAILABLE = False
    IMPORT_ERROR = str(e)

# Debug: print import status
print(f"[EdQuest] Generator available: {GENERATOR_AVAILABLE}, Anthropic available: {ANTHROPIC_AVAILABLE}")

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max


def get_api_key():
    """Get API key at request time, not module load time."""
    return os.environ.get('ANTHROPIC_API_KEY')


def check_api_key():
    """Check if API key is configured and return status info."""
    if not GENERATOR_AVAILABLE:
        return {
            'configured': False,
            'message': f'Generator module not available: {IMPORT_ERROR}'
        }
    api_key = get_api_key()
    if not api_key:
        return {
            'configured': False,
            'message': 'ANTHROPIC_API_KEY environment variable not set. AI generation disabled.'
        }
    if not ANTHROPIC_AVAILABLE:
        return {
            'configured': False,
            'message': 'anthropic package not installed.'
        }
    return {
        'configured': True,
        'message': 'Claude AI integration ready'
    }


def fetch_url_content(url):
    """Fetch text content from a URL."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get('content-type', '').lower()

        if 'text/html' in content_type:
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                    self.skip_tags = {'script', 'style', 'nav', 'header', 'footer'}
                    self.current_skip = False

                def handle_starttag(self, tag, attrs):
                    if tag in self.skip_tags:
                        self.current_skip = True

                def handle_endtag(self, tag):
                    if tag in self.skip_tags:
                        self.current_skip = False

                def handle_data(self, data):
                    if not self.current_skip:
                        text = data.strip()
                        if text:
                            self.text_parts.append(text)

            extractor = TextExtractor()
            extractor.feed(response.text)
            return ' '.join(extractor.text_parts)
        else:
            return response.text
    except Exception as e:
        return f"[Error fetching URL: {str(e)}]"


def process_content_sources(sources):
    """Process content sources and combine into single text."""
    all_content = []

    for source in sources:
        source_type = source.get('type', '')
        title = source.get('title', 'Untitled')

        if source_type == 'text':
            content = source.get('content', '')
            if content:
                all_content.append(f"--- SOURCE: {title} ---\n{content}")

        elif source_type == 'url':
            url = source.get('url', '')
            if url:
                content = fetch_url_content(url)
                all_content.append(f"--- SOURCE: {title} (from {url}) ---\n{content}")

        elif source_type == 'file':
            content = source.get('content', '')
            if content:
                all_content.append(f"--- SOURCE: {title} ---\n{content}")

    return '\n\n'.join(all_content)


@app.route('/api/test', methods=['GET'])
def api_test():
    """Simple test endpoint to verify API is working."""
    api_key = get_api_key()
    return jsonify({
        'status': 'ok',
        'generator_available': GENERATOR_AVAILABLE,
        'anthropic_available': ANTHROPIC_AVAILABLE,
        'api_key_set': bool(api_key),
        'api_key_length': len(api_key) if api_key else 0,
        'import_error': IMPORT_ERROR if not GENERATOR_AVAILABLE else None
    })


@app.route('/api/status', methods=['GET'])
def api_status():
    """Return API status including AI availability."""
    status = check_api_key()
    return jsonify(status)


@app.route('/api/generate', methods=['POST'])
def generate_scenario():
    """Generate a Twine scenario from JSON input."""
    try:
        if not GENERATOR_AVAILABLE:
            return jsonify({'error': f'Generator not available: {IMPORT_ERROR}'}), 500

        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Extract and validate fields
        theme = data.get('theme', '').strip()
        learning_objectives = data.get('learning_objectives', [])
        key_concepts = data.get('key_concepts', [])
        passing_threshold = data.get('passing_threshold', 70)
        default_points = data.get('default_points', 10)
        content_sources = data.get('content_sources', [])

        decision_nodes = data.get('decision_nodes', 4)
        branches_per_node = data.get('branches_per_node', 3)
        case_study_mode = data.get('case_study_mode', False)
        case_study = data.get('case_study', None)
        custom_scenario_description = data.get('custom_scenario_description', '')

        # Validation
        if not theme:
            return jsonify({'error': 'Theme is required'}), 400
        if not learning_objectives:
            return jsonify({'error': 'At least one learning objective is required'}), 400
        if not key_concepts:
            return jsonify({'error': 'At least one key concept is required'}), 400

        if case_study_mode:
            if not case_study or not case_study.get('content'):
                return jsonify({'error': 'Case study content is required in Case Study Mode'}), 400
        else:
            if not content_sources:
                return jsonify({'error': 'At least one content source is required'}), 400

        source_content = process_content_sources(content_sources)

        content = EducationalContent.from_dict({
            'theme': theme,
            'learning_objectives': learning_objectives,
            'key_concepts': key_concepts,
            'passing_threshold': passing_threshold,
            'default_points': default_points,
            'source_content': source_content
        })

        api_key = get_api_key()

        # Debug logging
        print(f"[EdQuest Generate] API key set: {bool(api_key)}, Anthropic available: {ANTHROPIC_AVAILABLE}")

        try:
            story = generate_educational_scenario(
                content, api_key,
                decision_nodes=decision_nodes,
                branches_per_node=branches_per_node,
                case_study_mode=case_study_mode,
                case_study=case_study,
                custom_scenario_description=custom_scenario_description
            )
            print("[EdQuest Generate] Generation completed successfully")
        except Exception as gen_error:
            print(f"[EdQuest Generate] AI generation failed: {type(gen_error).__name__}: {gen_error}")
            import traceback
            traceback.print_exc()
            story = generate_educational_scenario(
                content, None,
                decision_nodes=decision_nodes,
                branches_per_node=branches_per_node
            )
            print("[EdQuest Generate] Fallback to template completed")

        html_content = story.generate_html()

        safe_theme = "".join(c for c in theme if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_theme = safe_theme.replace(' ', '_')[:50] or 'scenario'
        output_filename = f"{safe_theme}_scenario.html"

        response = Response(html_content, mimetype='text/html')
        response.headers['Content-Disposition'] = f'attachment; filename="{output_filename}"'
        return response

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/preview', methods=['POST'])
def preview_scenario():
    """Generate and return HTML content for preview."""
    try:
        if not GENERATOR_AVAILABLE:
            return jsonify({'error': f'Generator not available: {IMPORT_ERROR}'}), 500

        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        theme = data.get('theme', '').strip()
        learning_objectives = data.get('learning_objectives', [])
        key_concepts = data.get('key_concepts', [])
        passing_threshold = data.get('passing_threshold', 70)
        default_points = data.get('default_points', 10)
        content_sources = data.get('content_sources', [])

        decision_nodes = data.get('decision_nodes', 4)
        branches_per_node = data.get('branches_per_node', 3)
        case_study_mode = data.get('case_study_mode', False)
        case_study = data.get('case_study', None)
        custom_scenario_description = data.get('custom_scenario_description', '')

        if not all([theme, learning_objectives, key_concepts]):
            return jsonify({'error': 'Theme, objectives, and concepts are required'}), 400

        if case_study_mode:
            if not case_study or not case_study.get('content'):
                return jsonify({'error': 'Case study content is required in Case Study Mode'}), 400
        else:
            if not content_sources:
                return jsonify({'error': 'At least one content source is required'}), 400

        source_content = process_content_sources(content_sources)

        content = EducationalContent.from_dict({
            'theme': theme,
            'learning_objectives': learning_objectives,
            'key_concepts': key_concepts,
            'passing_threshold': passing_threshold,
            'default_points': default_points,
            'source_content': source_content
        })

        api_key = get_api_key()

        # Debug logging
        print(f"[EdQuest Preview] API key set: {bool(api_key)}, Anthropic available: {ANTHROPIC_AVAILABLE}")

        try:
            story = generate_educational_scenario(
                content, api_key,
                decision_nodes=decision_nodes,
                branches_per_node=branches_per_node,
                case_study_mode=case_study_mode,
                case_study=case_study,
                custom_scenario_description=custom_scenario_description
            )
            print("[EdQuest Preview] Generation completed successfully")
        except Exception as gen_error:
            print(f"[EdQuest Preview] AI generation failed: {type(gen_error).__name__}: {gen_error}")
            import traceback
            traceback.print_exc()
            story = generate_educational_scenario(
                content, None,
                decision_nodes=decision_nodes,
                branches_per_node=branches_per_node
            )

        html_content = story.generate_html()

        return jsonify({'html': html_content})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# Vercel Python runtime automatically detects and uses the Flask 'app' variable
# No custom handler needed - just export 'app' at module level

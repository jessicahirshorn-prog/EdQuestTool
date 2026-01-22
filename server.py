"""
EdQuest Web Server
Flask backend for the Twine Generator web interface.
Uses Claude AI for immersive scenario generation.
"""

import os
import json
import tempfile
import requests
from flask import Flask, request, jsonify, send_file, send_from_directory
from twine_generator import EducationalContent, generate_educational_scenario, ANTHROPIC_AVAILABLE

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Get API key from environment
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')


def check_api_key():
    """Check if API key is configured and return status info."""
    if not ANTHROPIC_API_KEY:
        return {
            'configured': False,
            'message': 'ANTHROPIC_API_KEY environment variable not set. AI generation disabled.'
        }
    if not ANTHROPIC_AVAILABLE:
        return {
            'configured': False,
            'message': 'anthropic package not installed. Run: pip install anthropic'
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
            # Basic HTML to text conversion
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


@app.route('/')
def index():
    """Serve the main web interface."""
    return send_from_directory('.', 'index.html')


@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files."""
    return send_from_directory('static', path)


@app.route('/api/status', methods=['GET'])
def api_status():
    """Return API status including AI availability."""
    status = check_api_key()
    return jsonify(status)


@app.route('/api/generate', methods=['POST'])
def generate_scenario():
    """Generate a Twine scenario from JSON input."""
    try:
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

        # New parameters for scenario structure
        decision_nodes = data.get('decision_nodes', 4)
        branches_per_node = data.get('branches_per_node', 3)

        # Case study mode
        case_study_mode = data.get('case_study_mode', False)
        case_study = data.get('case_study', None)

        # Validation
        if not theme:
            return jsonify({'error': 'Theme is required'}), 400
        if not learning_objectives:
            return jsonify({'error': 'At least one learning objective is required'}), 400
        if not key_concepts:
            return jsonify({'error': 'At least one key concept is required'}), 400

        # Validate based on mode
        if case_study_mode:
            if not case_study or not case_study.get('content'):
                return jsonify({'error': 'Case study content is required in Case Study Mode'}), 400
        else:
            if not content_sources:
                return jsonify({'error': 'At least one content source is required'}), 400

        # Process content sources
        source_content = process_content_sources(content_sources)

        # Create educational content
        content = EducationalContent.from_dict({
            'theme': theme,
            'learning_objectives': learning_objectives,
            'key_concepts': key_concepts,
            'passing_threshold': passing_threshold,
            'default_points': default_points,
            'source_content': source_content
        })

        # Generate the story with AI if available
        api_key = ANTHROPIC_API_KEY if ANTHROPIC_AVAILABLE else None

        try:
            story = generate_educational_scenario(
                content, api_key,
                decision_nodes=decision_nodes,
                branches_per_node=branches_per_node,
                case_study_mode=case_study_mode,
                case_study=case_study
            )
        except Exception as gen_error:
            # If AI generation fails, it will fall back to template
            print(f"Generation error (using fallback): {gen_error}")
            story = generate_educational_scenario(
                content, None,
                decision_nodes=decision_nodes,
                branches_per_node=branches_per_node
            )

        html_content = story.generate_html()

        # Create safe filename
        safe_theme = "".join(c for c in theme if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_theme = safe_theme.replace(' ', '_')[:50] or 'scenario'
        output_filename = f"{safe_theme}_scenario.html"

        # Save to temp file and send
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.html', encoding='utf-8') as tmp:
            tmp.write(html_content)
            tmp_path = tmp.name

        response = send_file(
            tmp_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype='text/html'
        )
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
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        theme = data.get('theme', '').strip()
        learning_objectives = data.get('learning_objectives', [])
        key_concepts = data.get('key_concepts', [])
        passing_threshold = data.get('passing_threshold', 70)
        default_points = data.get('default_points', 10)
        content_sources = data.get('content_sources', [])

        # New parameters
        decision_nodes = data.get('decision_nodes', 4)
        branches_per_node = data.get('branches_per_node', 3)
        case_study_mode = data.get('case_study_mode', False)
        case_study = data.get('case_study', None)

        # Validation
        if not all([theme, learning_objectives, key_concepts]):
            return jsonify({'error': 'Theme, objectives, and concepts are required'}), 400

        # Validate based on mode
        if case_study_mode:
            if not case_study or not case_study.get('content'):
                return jsonify({'error': 'Case study content is required in Case Study Mode'}), 400
        else:
            if not content_sources:
                return jsonify({'error': 'At least one content source is required'}), 400

        # Process content sources
        source_content = process_content_sources(content_sources)

        # Create educational content
        content = EducationalContent.from_dict({
            'theme': theme,
            'learning_objectives': learning_objectives,
            'key_concepts': key_concepts,
            'passing_threshold': passing_threshold,
            'default_points': default_points,
            'source_content': source_content
        })

        # Generate with AI if available
        api_key = ANTHROPIC_API_KEY if ANTHROPIC_AVAILABLE else None

        try:
            story = generate_educational_scenario(
                content, api_key,
                decision_nodes=decision_nodes,
                branches_per_node=branches_per_node,
                case_study_mode=case_study_mode,
                case_study=case_study
            )
        except Exception as gen_error:
            print(f"Generation error (using fallback): {gen_error}")
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


if __name__ == '__main__':
    print("=" * 60)
    print("EdQuest Twine Generator - AI-Powered Web Interface")
    print("=" * 60)

    # Check API key status
    api_status = check_api_key()
    if api_status['configured']:
        print(f"\n[OK] {api_status['message']}")
    else:
        print(f"\n[WARNING] {api_status['message']}")
        print("         Scenarios will use template-based generation.")

    print("\nOpen http://localhost:5000 in your browser")
    print("Press Ctrl+C to stop the server\n")
    print("=" * 60)

    app.run(debug=True, port=5000)

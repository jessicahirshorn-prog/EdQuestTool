"""
EdQuest Twine 2 HTML Generator
Generates deep, immersive educational branching scenarios from source content.

Uses Claude AI to create complex, character-driven scenarios where students
become the protagonist and must apply knowledge from case studies and source materials.
Features multiple decision chains per concept with cause-and-effect consequences.
"""

import html
import json
import uuid
import re
import os
import argparse
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

# Optional anthropic import - will be checked at runtime
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


@dataclass
class Choice:
    """Represents a choice/link in a passage."""
    text: str
    target_passage: str

    def to_twine_link(self) -> str:
        """Convert to Twine link format."""
        if self.text == self.target_passage:
            return f"[[{self.text}]]"
        return f"[[{self.text}->{self.target_passage}]]"


@dataclass
class Passage:
    """Represents a single passage in the story."""
    name: str
    content: str
    choices: list[Choice] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    position_x: int = 100
    position_y: int = 100

    def get_full_content(self) -> str:
        """Get passage content with choices appended."""
        parts = [self.content]
        if self.choices:
            choice_links = [choice.to_twine_link() for choice in self.choices]
            parts.append("\n\n" + "\n".join(choice_links))
        return "".join(parts)


@dataclass
class GradingConfig:
    """Configuration for grading in generated scenarios."""
    enabled: bool = False
    concept_points: dict = field(default_factory=dict)
    passing_threshold: int = 70
    total_points: int = 0
    passing_points: int = 0


@dataclass
class TwineStory:
    """Represents a complete Twine story."""
    title: str
    passages: list[Passage] = field(default_factory=list)
    start_passage: Optional[str] = None
    ifid: Optional[str] = None
    grading: Optional[GradingConfig] = None

    def __post_init__(self):
        if self.ifid is None:
            self.ifid = str(uuid.uuid4()).upper()

    def add_passage(self, passage: Passage) -> None:
        """Add a passage to the story."""
        self.passages.append(passage)

    def get_start_passage_index(self) -> int:
        """Get the index of the starting passage (1-based for Twine)."""
        if not self.passages:
            return 1
        start_name = self.start_passage or (self.passages[0].name if self.passages else "Start")
        for i, passage in enumerate(self.passages):
            if passage.name == start_name:
                return i + 1
        return 1

    def generate_html(self) -> str:
        """Generate complete Twine 2 HTML file."""
        passage_elements = []
        for i, passage in enumerate(self.passages, start=1):
            tags = " ".join(passage.tags) if passage.tags else ""
            content = html.escape(passage.get_full_content())
            passage_html = (
                f'<tw-passagedata pid="{i}" name="{html.escape(passage.name)}" '
                f'tags="{html.escape(tags)}" position="{passage.position_x},{passage.position_y}" '
                f'size="100,100">{content}</tw-passagedata>'
            )
            passage_elements.append(passage_html)

        passages_html = "\n".join(passage_elements)
        start_node = self.get_start_passage_index()

        grading_script = ""
        if self.grading and self.grading.enabled:
            grading_json = json.dumps({
                "enabled": True,
                "conceptPoints": self.grading.concept_points,
                "passingThreshold": self.grading.passing_threshold,
                "totalPoints": self.grading.total_points,
                "passingPoints": self.grading.passing_points
            })
            grading_script = f"const GRADING_CONFIG = {grading_json};"
        else:
            grading_script = "const GRADING_CONFIG = {enabled: false};"

        html_output = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{html.escape(self.title)}</title>
<style>
body {{
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
}}
tw-story {{
    display: block;
    max-width: 800px;
    margin: 0 auto;
    padding: 40px 20px;
}}
tw-passage {{
    display: block;
    background: white;
    border-radius: 16px;
    padding: 32px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.2);
}}
tw-passage p {{
    margin: 0 0 16px 0;
    line-height: 1.7;
    color: #333;
}}
tw-passage p:last-child {{
    margin-bottom: 0;
}}
/* Fixed: Choice buttons with proper text wrapping */
tw-link {{
    display: block;
    padding: 16px 20px;
    margin: 8px 0;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    text-decoration: none;
    border-radius: 8px;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
    font-weight: 500;
    white-space: normal;
    word-wrap: break-word;
    overflow-wrap: break-word;
    line-height: 1.4;
}}
tw-link:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}}
/* Navigation buttons */
.nav-buttons {{
    display: flex;
    gap: 12px;
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid #eee;
}}
.nav-btn {{
    padding: 10px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 500;
    transition: all 0.2s;
    border: none;
}}
.nav-btn-back {{
    background: #e5e7eb;
    color: #374151;
}}
.nav-btn-back:hover {{
    background: #d1d5db;
}}
.nav-btn-restart {{
    background: #fee2e2;
    color: #dc2626;
}}
.nav-btn-restart:hover {{
    background: #fecaca;
}}
.scenario-context {{
    background: #f8f9fa;
    border-left: 4px solid #667eea;
    padding: 16px;
    margin-bottom: 20px;
    border-radius: 0 8px 8px 0;
}}
.character-dialogue {{
    background: #e8f4f8;
    border-left: 4px solid #17a2b8;
    padding: 16px;
    margin: 16px 0;
    border-radius: 0 8px 8px 0;
    font-style: italic;
}}
.character-name {{
    font-weight: bold;
    color: #0c5460;
    font-style: normal;
}}
.decision-prompt {{
    font-weight: 600;
    color: #333;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid #eee;
}}
.feedback-correct {{
    background: #d4edda;
    border-left: 4px solid #28a745;
    padding: 16px;
    margin-bottom: 20px;
    border-radius: 0 8px 8px 0;
}}
.feedback-incorrect {{
    background: #f8d7da;
    border-left: 4px solid #dc3545;
    padding: 16px;
    margin-bottom: 20px;
    border-radius: 0 8px 8px 0;
}}
.feedback-partial {{
    background: #fff3cd;
    border-left: 4px solid #ffc107;
    padding: 16px;
    margin-bottom: 20px;
    border-radius: 0 8px 8px 0;
}}
.source-reference {{
    background: #fff3cd;
    border-left: 4px solid #ffc107;
    padding: 12px 16px;
    margin: 16px 0;
    border-radius: 0 8px 8px 0;
    font-size: 0.9em;
}}
.consequence {{
    background: #e2e3e5;
    border-left: 4px solid #6c757d;
    padding: 12px 16px;
    margin: 16px 0;
    border-radius: 0 8px 8px 0;
}}
.theme-atmosphere {{
    background: linear-gradient(135deg, #f3e8ff 0%, #e9d5ff 100%);
    border-left: 4px solid #9333ea;
    padding: 14px 16px;
    margin: 16px 0;
    border-radius: 0 8px 8px 0;
    font-style: italic;
    color: #581c87;
}}
.points-earned {{
    display: inline-block;
    background: #28a745;
    color: white;
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: bold;
    font-size: 0.9em;
}}
.points-missed {{
    display: inline-block;
    background: #dc2626;
    color: white;
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: bold;
    font-size: 0.9em;
}}
.points-partial {{
    display: inline-block;
    background: #f59e0b;
    color: white;
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: bold;
    font-size: 0.9em;
}}
.score-display {{
    position: fixed;
    top: 20px;
    right: 20px;
    background: white;
    padding: 16px 24px;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    z-index: 1000;
    text-align: center;
}}
.score-display .label {{
    font-size: 12px;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 1px;
}}
.score-display .value {{
    font-size: 28px;
    font-weight: bold;
    color: #667eea;
}}
.results-box {{
    background: #f8f9fa;
    border-radius: 12px;
    padding: 24px;
    margin: 20px 0;
}}
.results-box.passed {{
    background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
}}
.results-box.failed {{
    background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
}}
.results-score {{
    font-size: 48px;
    font-weight: bold;
    text-align: center;
}}
.results-box.passed .results-score {{ color: #28a745; }}
.results-box.failed .results-score {{ color: #dc3545; }}
.results-status {{
    text-align: center;
    font-size: 20px;
    font-weight: 600;
    margin: 10px 0 20px;
}}
.concept-result {{
    display: flex;
    justify-content: space-between;
    padding: 10px 14px;
    background: white;
    border-radius: 6px;
    margin-bottom: 8px;
}}
.concept-result.correct {{ border-left: 4px solid #28a745; }}
.concept-result.incorrect {{ border-left: 4px solid #dc3545; }}
.concept-result.partial {{ border-left: 4px solid #f59e0b; }}
.chapter-header {{
    background: linear-gradient(135deg, #1e3a8a 0%, #3730a3 100%);
    color: white;
    padding: 16px 20px;
    margin: -32px -32px 24px -32px;
    border-radius: 16px 16px 0 0;
}}
.chapter-header h2 {{
    margin: 0;
    font-size: 1.1rem;
    font-weight: 600;
}}
.chapter-header .chapter-num {{
    opacity: 0.8;
    font-size: 0.85rem;
}}
</style>
</head>
<body>
<tw-storydata name="{html.escape(self.title)}" startnode="{start_node}" creator="EdQuest"
creator-version="2.0.0" ifid="{self.ifid}" zoom="1" format="Harlowe" format-version="3.3.9"
options="" tags="" hidden>
<style role="stylesheet" id="twine-user-stylesheet" type="text/twine-css"></style>
<script role="script" id="twine-user-script" type="text/twine-javascript"></script>
{passages_html}
</tw-storydata>
<script>
{grading_script}
{HARLOWE_ENGINE}
</script>
</body>
</html>'''
        return html_output


HARLOWE_ENGINE = '''
(function() {
    const storyData = document.querySelector('tw-storydata');
    const passages = {};
    const history = [];

    storyData.querySelectorAll('tw-passagedata').forEach(p => {
        passages[p.getAttribute('name')] = {
            pid: p.getAttribute('pid'),
            content: p.textContent,
            tags: (p.getAttribute('tags') || '').split(' ').filter(t => t)
        };
    });

    const startNode = storyData.getAttribute('startnode');
    let startPassage = null;
    for (const [name, data] of Object.entries(passages)) {
        if (data.pid === startNode) {
            startPassage = name;
            break;
        }
    }

    const grading = {
        enabled: typeof GRADING_CONFIG !== 'undefined' && GRADING_CONFIG.enabled,
        config: typeof GRADING_CONFIG !== 'undefined' ? GRADING_CONFIG : {},
        score: 0,
        conceptResults: {},
        initialized: false
    };

    if (grading.enabled) {
        for (const [concept, points] of Object.entries(grading.config.conceptPoints || {})) {
            grading.conceptResults[concept] = { correct: false, points: points, earned: 0, attempts: 0, answered: false };
        }
    }

    let scoreDisplay = null;
    if (grading.enabled) {
        scoreDisplay = document.createElement('div');
        scoreDisplay.className = 'score-display';
        scoreDisplay.innerHTML = '<div class="label">Score</div><div class="value">0</div><div class="label">of ' + grading.config.totalPoints + '</div>';
        document.body.appendChild(scoreDisplay);
    }

    function updateScoreDisplay() {
        if (scoreDisplay) {
            scoreDisplay.querySelector('.value').textContent = grading.score;
        }
    }

    function getConceptFromPassage(passageName) {
        // Match patterns like "Correct 1", "Incorrect 2a", "Partial 1b"
        const match = passageName.match(/(Correct|Incorrect|Partial)\\s+(\\d+)/);
        if (match) {
            const num = parseInt(match[2]);
            const concepts = Object.keys(grading.config.conceptPoints || {});
            if (num <= concepts.length) {
                return {
                    concept: concepts[num - 1],
                    isCorrect: match[1] === 'Correct',
                    isPartial: match[1] === 'Partial'
                };
            }
        }
        return null;
    }

    const storyEl = document.createElement('tw-story');
    document.body.appendChild(storyEl);

    function showPassage(name, addToHistory = true) {
        const passage = passages[name];
        if (!passage) {
            storyEl.innerHTML = '<tw-passage><p>Error: Passage not found: ' + name + '</p></tw-passage>';
            return;
        }

        if (addToHistory && history[history.length - 1] !== name) {
            history.push(name);
        }

        if (grading.enabled) {
            const conceptInfo = getConceptFromPassage(name);
            if (conceptInfo && grading.conceptResults[conceptInfo.concept]) {
                const result = grading.conceptResults[conceptInfo.concept];
                result.attempts++;
                if (!result.answered) {
                    if (conceptInfo.isCorrect) {
                        result.correct = true;
                        result.answered = true;
                        result.earned = result.points;
                        grading.score += result.points;
                        updateScoreDisplay();
                    } else if (conceptInfo.isPartial) {
                        result.answered = true;
                        result.earned = Math.floor(result.points * 0.5);
                        grading.score += result.earned;
                        updateScoreDisplay();
                    }
                }
            }
        }

        let content = passage.content;

        if (name === 'Results' && grading.enabled) {
            content = generateResultsContent();
        }

        content = content.replace(/\\[\\[([^\\]]+)->([^\\]]+)\\]\\]/g, (match, text, target) => {
            return '<tw-link data-target="' + target + '">' + text + '</tw-link>';
        });
        content = content.replace(/\\[\\[([^\\]]+)\\]\\]/g, (match, target) => {
            return '<tw-link data-target="' + target + '">' + target + '</tw-link>';
        });

        if (grading.enabled) {
            content = content.replace(/\\{SCORE\\}/g, grading.score);
            content = content.replace(/\\{TOTAL\\}/g, grading.config.totalPoints);
            content = content.replace(/\\{PERCENTAGE\\}/g, Math.round((grading.score / grading.config.totalPoints) * 100));
            content = content.replace(/\\{PASSING\\}/g, grading.config.passingThreshold);
            content = content.replace(/\\{RESULTS_BOX\\}/g, generateResultsBox());
        }

        content = content.split('\\n\\n').map(p => '<p>' + p.replace(/\\n/g, '<br>') + '</p>').join('');

        // Add navigation buttons (except on Start and Results)
        let navButtons = '';
        if (name !== 'Start' && name !== 'Results') {
            navButtons = '<div class="nav-buttons">';
            if (history.length > 1) {
                navButtons += '<button class="nav-btn nav-btn-back" onclick="goBack()">Go Back</button>';
            }
            navButtons += '<button class="nav-btn nav-btn-restart" onclick="resetScenario()">Start Again</button>';
            navButtons += '</div>';
        }

        const passageEl = document.createElement('tw-passage');
        passageEl.innerHTML = content + navButtons;

        storyEl.innerHTML = '';
        storyEl.appendChild(passageEl);

        passageEl.querySelectorAll('tw-link').forEach(link => {
            link.addEventListener('click', () => {
                showPassage(link.getAttribute('data-target'));
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
        });
    }

    function generateResultsBox() {
        if (!grading.enabled) return '';
        const percentage = Math.round((grading.score / grading.config.totalPoints) * 100);
        const passed = percentage >= grading.config.passingThreshold;
        const statusClass = passed ? 'passed' : 'failed';
        const statusText = passed ? 'PASSED' : 'NEEDS REVIEW';

        let conceptBreakdown = '';
        for (const [concept, result] of Object.entries(grading.conceptResults)) {
            let cls = result.correct ? 'correct' : (result.earned > 0 ? 'partial' : 'incorrect');
            let icon = result.correct ? '\\u2713' : (result.earned > 0 ? '~' : '\\u2717');
            let pts = result.earned > 0 ? '+' + result.earned : '0';
            conceptBreakdown += '<div class="concept-result ' + cls + '"><span>' + icon + ' ' + concept + '</span><span>' + pts + ' / ' + result.points + ' pts</span></div>';
        }

        return '<div class="results-box ' + statusClass + '">' +
            '<div class="results-score">' + percentage + '%</div>' +
            '<div class="results-status">' + statusText + '</div>' +
            '<div><strong>Score:</strong> ' + grading.score + ' / ' + grading.config.totalPoints + ' points</div>' +
            '<div><strong>Required:</strong> ' + grading.config.passingThreshold + '%</div>' +
            '<div style="margin-top:16px"><strong>Concept Breakdown:</strong></div>' +
            conceptBreakdown + '</div>';
    }

    function generateResultsContent() {
        return '**Your Results**\\n\\n{RESULTS_BOX}';
    }

    window.goBack = function() {
        if (history.length > 1) {
            history.pop(); // Remove current
            const previous = history[history.length - 1];
            showPassage(previous, false);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    };

    window.resetScenario = function() {
        grading.score = 0;
        history.length = 0;
        for (const concept of Object.keys(grading.conceptResults)) {
            grading.conceptResults[concept] = {
                correct: false,
                points: grading.conceptResults[concept].points,
                earned: 0,
                attempts: 0,
                answered: false
            };
        }
        updateScoreDisplay();
        showPassage(startPassage);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    if (startPassage) {
        showPassage(startPassage);
    }
})();
'''


@dataclass
class ConceptWithPoints:
    """Represents a key concept with its point value."""
    name: str
    points: int = 10


@dataclass
class EducationalContent:
    """Represents educational content for scenario generation."""
    theme: str
    learning_objectives: list[str]
    key_concepts: list[ConceptWithPoints]
    source_content: str = ""
    passing_threshold: int = 70
    default_points: int = 10

    @property
    def total_points(self) -> int:
        return sum(c.points for c in self.key_concepts)

    @property
    def passing_points(self) -> int:
        return int(self.total_points * self.passing_threshold / 100)

    @property
    def concept_names(self) -> list[str]:
        return [c.name for c in self.key_concepts]

    def extract_key_terms(self) -> list[str]:
        """Extract key terms from source content for use in scenarios."""
        if not self.source_content:
            return []
        common_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her',
                       'was', 'one', 'our', 'out', 'has', 'have', 'been', 'were', 'they', 'their',
                       'what', 'when', 'where', 'who', 'will', 'with', 'this', 'that', 'from', 'which'}
        words = re.findall(r'\b[a-zA-Z]{5,}\b', self.source_content.lower())
        word_freq = {}
        for w in words:
            if w not in common_words:
                word_freq[w] = word_freq.get(w, 0) + 1
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:20]]

    @classmethod
    def from_dict(cls, data: dict) -> 'EducationalContent':
        """Load educational content from a dictionary."""
        required_fields = ['theme', 'learning_objectives', 'key_concepts']
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"Missing required field: {field_name}")

        default_points = data.get('default_points', 10)
        key_concepts = []
        for concept in data['key_concepts']:
            if isinstance(concept, str):
                key_concepts.append(ConceptWithPoints(name=concept, points=default_points))
            elif isinstance(concept, dict):
                key_concepts.append(ConceptWithPoints(
                    name=concept.get('name', ''),
                    points=concept.get('points', default_points)
                ))

        return cls(
            theme=data['theme'],
            learning_objectives=data['learning_objectives'],
            key_concepts=key_concepts,
            source_content=data.get('source_content', ''),
            passing_threshold=data.get('passing_threshold', 70),
            default_points=default_points
        )

    @classmethod
    def from_json_file(cls, filepath: str) -> 'EducationalContent':
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


def get_theme_context(theme: str) -> dict:
    """Get detailed theme context for deep integration."""
    theme_lower = theme.lower()

    theme_contexts = {
        'space': {
            'setting': 'aboard a deep space research vessel or space station',
            'role': 'newly assigned crew member/specialist',
            'atmosphere': 'The hum of life support systems fills the air. Through the viewport, stars stretch infinitely into the void.',
            'npcs': ['Commander', 'Chief Science Officer', 'Medical Officer', 'Engineer', 'AI System'],
            'elements': ['zero gravity', 'airlocks', 'communication delays', 'resource management', 'cosmic phenomena'],
            'stakes': 'crew safety, mission success, survival in the void'
        },
        'adventure': {
            'setting': 'an uncharted wilderness or ancient ruins',
            'role': 'expedition leader/explorer',
            'atmosphere': 'The unknown stretches before you, full of both promise and peril. Every decision could lead to discovery or disaster.',
            'npcs': ['Local Guide', 'Veteran Explorer', 'Scholar', 'Team Member', 'Mysterious Stranger'],
            'elements': ['environmental hazards', 'limited supplies', 'ancient mysteries', 'team dynamics', 'moral dilemmas'],
            'stakes': 'team safety, discovery, ethical choices'
        },
        'time travel': {
            'setting': 'various historical periods accessed through temporal displacement',
            'role': 'temporal agent/researcher',
            'atmosphere': 'The temporal field shimmers around you as history unfolds. Every action ripples through time.',
            'npcs': ['Mission Control', 'Historical Figure', 'Fellow Agent', 'Local Contact', 'Temporal Guardian'],
            'elements': ['historical accuracy', 'paradox prevention', 'cultural sensitivity', 'timeline preservation', 'ethical implications'],
            'stakes': 'timeline integrity, historical preservation, preventing paradoxes'
        },
        'detective': {
            'setting': 'crime scenes, interrogation rooms, and investigation sites',
            'role': 'lead investigator/detective',
            'atmosphere': 'Clues hide in plain sight. Every witness has a story, and somewhere in the details lies the truth.',
            'npcs': ['Partner', 'Witness', 'Suspect', 'Forensic Specialist', 'Informant'],
            'elements': ['evidence analysis', 'witness interviews', 'logical deduction', 'time pressure', 'moral gray areas'],
            'stakes': 'justice, truth, protecting the innocent'
        },
        'mystery': {
            'setting': 'crime scenes, interrogation rooms, and investigation sites',
            'role': 'lead investigator/detective',
            'atmosphere': 'Clues hide in plain sight. Every witness has a story, and somewhere in the details lies the truth.',
            'npcs': ['Partner', 'Witness', 'Suspect', 'Forensic Specialist', 'Informant'],
            'elements': ['evidence analysis', 'witness interviews', 'logical deduction', 'time pressure', 'moral gray areas'],
            'stakes': 'justice, truth, protecting the innocent'
        },
        'intercultural': {
            'setting': 'international summits, cultural exchanges, or global organizations',
            'role': 'cultural liaison/diplomat',
            'atmosphere': 'Diverse perspectives converge here. Understanding bridges gaps; assumptions create chasms.',
            'npcs': ['Cultural Representative', 'Translator', 'Local Leader', 'International Colleague', 'Community Elder'],
            'elements': ['cultural protocols', 'communication styles', 'values differences', 'relationship building', 'conflict resolution'],
            'stakes': 'international relations, mutual understanding, peaceful cooperation'
        },
        'global': {
            'setting': 'international summits, cultural exchanges, or global organizations',
            'role': 'cultural liaison/diplomat',
            'atmosphere': 'Diverse perspectives converge here. Understanding bridges gaps; assumptions create chasms.',
            'npcs': ['Cultural Representative', 'Translator', 'Local Leader', 'International Colleague', 'Community Elder'],
            'elements': ['cultural protocols', 'communication styles', 'values differences', 'relationship building', 'conflict resolution'],
            'stakes': 'international relations, mutual understanding, peaceful cooperation'
        },
        'non-profit': {
            'setting': 'community centers, field operations, or organizational headquarters',
            'role': 'program coordinator/field worker',
            'atmosphere': 'Resources are limited but dedication runs deep. Every decision affects real lives and communities.',
            'npcs': ['Executive Director', 'Community Member', 'Volunteer', 'Donor Representative', 'Partner Organization Lead'],
            'elements': ['resource allocation', 'stakeholder management', 'ethical fundraising', 'impact measurement', 'community engagement'],
            'stakes': 'community welfare, organizational sustainability, mission integrity'
        },
        'ngo': {
            'setting': 'community centers, field operations, or organizational headquarters',
            'role': 'program coordinator/field worker',
            'atmosphere': 'Resources are limited but dedication runs deep. Every decision affects real lives and communities.',
            'npcs': ['Executive Director', 'Community Member', 'Volunteer', 'Donor Representative', 'Partner Organization Lead'],
            'elements': ['resource allocation', 'stakeholder management', 'ethical fundraising', 'impact measurement', 'community engagement'],
            'stakes': 'community welfare, organizational sustainability, mission integrity'
        },
        'healthcare': {
            'setting': 'hospital wards, clinics, or medical facilities',
            'role': 'healthcare professional (resident, nurse, specialist)',
            'atmosphere': 'The weight of responsibility presses in. Lives hang in the balance of your expertise and judgment.',
            'npcs': ['Attending Physician', 'Nurse', 'Patient', 'Family Member', 'Specialist Consultant'],
            'elements': ['patient care', 'medical ethics', 'time pressure', 'team communication', 'evidence-based practice'],
            'stakes': 'patient outcomes, ethical care, professional integrity'
        },
        'clinical': {
            'setting': 'hospital wards, clinics, or medical facilities',
            'role': 'healthcare professional (resident, nurse, specialist)',
            'atmosphere': 'The weight of responsibility presses in. Lives hang in the balance of your expertise and judgment.',
            'npcs': ['Attending Physician', 'Nurse', 'Patient', 'Family Member', 'Specialist Consultant'],
            'elements': ['patient care', 'medical ethics', 'time pressure', 'team communication', 'evidence-based practice'],
            'stakes': 'patient outcomes, ethical care, professional integrity'
        },
        'business': {
            'setting': 'corporate offices, boardrooms, or business operations',
            'role': 'manager/analyst/consultant',
            'atmosphere': 'Competing priorities demand attention. Stakeholders watch closely as strategy meets reality.',
            'npcs': ['Executive', 'Team Member', 'Client', 'Competitor', 'Mentor'],
            'elements': ['strategic decisions', 'stakeholder management', 'resource constraints', 'ethical dilemmas', 'market dynamics'],
            'stakes': 'business success, team welfare, ethical conduct'
        },
        'corporate': {
            'setting': 'corporate offices, boardrooms, or business operations',
            'role': 'manager/analyst/consultant',
            'atmosphere': 'Competing priorities demand attention. Stakeholders watch closely as strategy meets reality.',
            'npcs': ['Executive', 'Team Member', 'Client', 'Competitor', 'Mentor'],
            'elements': ['strategic decisions', 'stakeholder management', 'resource constraints', 'ethical dilemmas', 'market dynamics'],
            'stakes': 'business success, team welfare, ethical conduct'
        },
        'research': {
            'setting': 'laboratories, research facilities, or field sites',
            'role': 'research scientist/assistant',
            'atmosphere': 'Data tells stories to those who listen carefully. Methodology separates discovery from delusion.',
            'npcs': ['Principal Investigator', 'Lab Technician', 'Peer Researcher', 'Ethics Board Member', 'Research Subject'],
            'elements': ['methodology', 'data integrity', 'ethical considerations', 'peer review', 'reproducibility'],
            'stakes': 'scientific integrity, research ethics, knowledge advancement'
        },
        'laboratory': {
            'setting': 'laboratories, research facilities, or field sites',
            'role': 'research scientist/assistant',
            'atmosphere': 'Data tells stories to those who listen carefully. Methodology separates discovery from delusion.',
            'npcs': ['Principal Investigator', 'Lab Technician', 'Peer Researcher', 'Ethics Board Member', 'Research Subject'],
            'elements': ['methodology', 'data integrity', 'ethical considerations', 'peer review', 'reproducibility'],
            'stakes': 'scientific integrity, research ethics, knowledge advancement'
        },
        'legal': {
            'setting': 'courtrooms, law offices, or compliance departments',
            'role': 'attorney/paralegal/compliance officer',
            'atmosphere': 'Precedent and principle collide. The letter of the law meets the spirit of justice.',
            'npcs': ['Senior Partner', 'Client', 'Opposing Counsel', 'Judge', 'Witness'],
            'elements': ['legal analysis', 'ethical obligations', 'client advocacy', 'procedural requirements', 'risk assessment'],
            'stakes': 'justice, client welfare, professional ethics'
        },
        'compliance': {
            'setting': 'courtrooms, law offices, or compliance departments',
            'role': 'attorney/paralegal/compliance officer',
            'atmosphere': 'Precedent and principle collide. The letter of the law meets the spirit of justice.',
            'npcs': ['Senior Partner', 'Client', 'Opposing Counsel', 'Judge', 'Witness'],
            'elements': ['legal analysis', 'ethical obligations', 'client advocacy', 'procedural requirements', 'risk assessment'],
            'stakes': 'justice, client welfare, professional ethics'
        },
        'educational': {
            'setting': 'classrooms, schools, or educational institutions',
            'role': 'teacher/administrator/counselor',
            'atmosphere': 'Young minds look to you for guidance. Every interaction shapes futures.',
            'npcs': ['Principal', 'Student', 'Parent', 'Colleague Teacher', 'Counselor'],
            'elements': ['pedagogical methods', 'student needs', 'classroom management', 'assessment', 'equity considerations'],
            'stakes': 'student success, educational equity, professional growth'
        },
        'teaching': {
            'setting': 'classrooms, schools, or educational institutions',
            'role': 'teacher/administrator/counselor',
            'atmosphere': 'Young minds look to you for guidance. Every interaction shapes futures.',
            'npcs': ['Principal', 'Student', 'Parent', 'Colleague Teacher', 'Counselor'],
            'elements': ['pedagogical methods', 'student needs', 'classroom management', 'assessment', 'equity considerations'],
            'stakes': 'student success, educational equity, professional growth'
        },
        'technical': {
            'setting': 'engineering facilities, tech companies, or project sites',
            'role': 'engineer/developer/technical lead',
            'atmosphere': 'Complex systems demand precision. Innovation pushes boundaries while safety sets limits.',
            'npcs': ['Project Manager', 'Senior Engineer', 'QA Specialist', 'Client Representative', 'Team Member'],
            'elements': ['technical constraints', 'safety requirements', 'innovation vs risk', 'team collaboration', 'deadline pressure'],
            'stakes': 'project success, safety, technical excellence'
        },
        'engineering': {
            'setting': 'engineering facilities, tech companies, or project sites',
            'role': 'engineer/developer/technical lead',
            'atmosphere': 'Complex systems demand precision. Innovation pushes boundaries while safety sets limits.',
            'npcs': ['Project Manager', 'Senior Engineer', 'QA Specialist', 'Client Representative', 'Team Member'],
            'elements': ['technical constraints', 'safety requirements', 'innovation vs risk', 'team collaboration', 'deadline pressure'],
            'stakes': 'project success, safety, technical excellence'
        }
    }

    # Find matching theme context
    for key, context in theme_contexts.items():
        if key in theme_lower:
            return context

    # Default generic context
    return {
        'setting': 'a professional environment',
        'role': 'a key decision-maker',
        'atmosphere': 'The situation demands your full attention and expertise.',
        'npcs': ['Supervisor', 'Colleague', 'Client', 'Expert', 'Stakeholder'],
        'elements': ['critical decisions', 'stakeholder interests', 'ethical considerations', 'time pressure', 'resource constraints'],
        'stakes': 'success, integrity, relationships'
    }


def generate_scenario_with_ai(content: EducationalContent, api_key: str,
                               decision_nodes: int = 4, branches_per_node: int = 3,
                               case_study_mode: bool = False, case_study: dict = None) -> dict:
    """
    Use Claude AI to generate an application-focused educational scenario
    with concise text and non-obvious choices that require critical thinking.
    """
    if not ANTHROPIC_AVAILABLE:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)

    # Get theme context
    theme_context = get_theme_context(content.theme)

    # Build the prompt for Claude
    concepts_list = "\n".join(f"- {c.name} ({c.points} points)" for c in content.key_concepts)
    objectives_list = "\n".join(f"- {obj}" for obj in content.learning_objectives)

    # Prepare source content
    source_text = content.source_content
    if len(source_text) > 20000:
        source_text = source_text[:20000] + "\n\n[Content truncated...]"

    # Prepare case study content if provided
    case_study_section = ""
    if case_study_mode and case_study:
        case_study_content = case_study.get('content', '')
        if len(case_study_content) > 15000:
            case_study_content = case_study_content[:15000] + "\n\n[Truncated...]"
        case_study_section = f"""
## CASE STUDY (PRIMARY SOURCE - BUILD SCENARIO AROUND THIS)
Title: {case_study.get('title', 'Case Study')}

{case_study_content}

CRITICAL: The scenario MUST be built around this case study. Use its specific:
- Characters, names, and roles
- Situations and events described
- Organizations and context
- Actual dilemmas and decisions faced
The student should feel they are living INSIDE this case, making the real decisions.
"""

    prompt = f"""You are creating an APPLICATION-FOCUSED educational scenario. Students must APPLY concepts through realistic decisions, not just recognize correct answers.

## CORE DESIGN PRINCIPLES

### 1. CONCISE TEXT - NO FLUFF
- Maximum 2-3 sentences per situation description
- Get to the decision point QUICKLY
- No flowery prose or unnecessary atmosphere
- Every sentence should either present information needed for the decision OR advance to the next choice

### 2. ALL CHOICES MUST SOUND REASONABLE
THIS IS CRITICAL. Do NOT make correct answers obvious by:
- Making wrong answers sound extreme, lazy, or unprofessional
- Using phrases like "ignore the problem" or "do nothing" for wrong choices
- Making the correct answer the only one that sounds competent
- Using obviously negative language for wrong choices

INSTEAD:
- Every choice should sound like something a reasonable professional might consider
- Wrong choices should reflect common misconceptions or incomplete understanding
- Choices differ in HOW they apply the concept, not WHETHER they're trying
- A student who hasn't studied should find all options equally plausible

### 3. APPLICATION OVER RECOGNITION
- Don't ask "which is the correct principle?" - that's recognition
- DO ask "given this situation, what action best applies [concept]?"
- Students must THINK about how the concept applies to THIS specific context
- Choices should represent different APPROACHES to applying the concept

### 4. DECISION-HEAVY STRUCTURE
- {decision_nodes} decision points per concept (not 2-3, but {decision_nodes})
- {branches_per_node} choices at each decision point
- Minimize reading, maximize choosing
- Each decision should flow quickly to the next

## Theme: {content.theme}
- Setting: {theme_context['setting']}
- Student Role: {theme_context['role']}
- Stakes: {theme_context['stakes']}
{case_study_section}
## SUPPLEMENTARY MATERIALS
{source_text if source_text else "(No additional materials provided)"}

## Learning Objectives (students must APPLY these)
{objectives_list}

## Key Concepts to Assess
{concepts_list}

## SCENARIO STRUCTURE

Create {len(content.key_concepts)} chapters, one per concept. Each chapter has:
- Brief setup (2-3 sentences max)
- {decision_nodes} connected decision points
- {branches_per_node} choices per decision (all sounding reasonable)
- Quick consequences leading to next decision

## JSON OUTPUT FORMAT

Return ONLY valid JSON:

{{
  "introduction": {{
    "situation": "1-2 sentences setting the scene",
    "role": "Your role in one sentence",
    "stakes": "What's at stake in one sentence"
  }},
  "chapters": [
    {{
      "concept": "Concept name being tested",
      "title": "Brief chapter title",
      "setup": "2-3 sentences establishing the situation",
      "decisions": [
        {{
          "situation": "1-2 sentences presenting the immediate situation",
          "prompt": "What do you do? (or specific question)",
          "choices": [
            {{
              "text": "Professional-sounding action A (max 60 chars)",
              "quality": "best",
              "consequence": "Brief outcome (1 sentence)",
              "feedback": "Why this was optimal - reference source material"
            }},
            {{
              "text": "Professional-sounding action B (max 60 chars)",
              "quality": "partial",
              "consequence": "Brief outcome showing partial success",
              "feedback": "What was missing in this approach"
            }},
            {{
              "text": "Professional-sounding action C (max 60 chars)",
              "quality": "poor",
              "consequence": "Brief outcome showing problem",
              "feedback": "Why this doesn't properly apply the concept"
            }}
          ],
          "concept_application": "How this tests application of the concept"
        }}
      ],
      "resolution": "One sentence wrapping up"
    }}
  ],
  "conclusion": {{
    "high_score": "Brief congratulations (1 sentence)",
    "medium_score": "Brief encouragement (1 sentence)",
    "low_score": "Brief redirect to review (1 sentence)"
  }}
}}

## CHOICE QUALITY EXAMPLES

BAD (obvious correct answer):
- "Carefully review all documentation before proceeding" (obviously good)
- "Skip the review and hope for the best" (obviously bad)
- "Ignore standard protocols" (obviously bad)

GOOD (all sound reasonable):
- "Review the full documentation set before the meeting"
- "Focus review on sections most relevant to today's agenda"
- "Request a meeting postponement to allow thorough review"

All three sound professional. The "best" one depends on applying the specific concept being tested.

## CRITICAL REMINDERS
1. {decision_nodes} decisions per concept, {branches_per_node} choices each
2. ALL choices must sound like reasonable professional options
3. Maximum 2-3 sentences per situation - be CONCISE
4. Test APPLICATION: "how would you apply X here?" not "what is X?"
5. Choice text max 60 characters
6. Return ONLY valid JSON"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=12000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        response_text = message.content[0].text

        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            scenario_data = json.loads(json_match.group())
            return scenario_data
        else:
            raise ValueError("No valid JSON found in AI response")

    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse AI response as JSON: {e}")
    except anthropic.APIError as e:
        raise RuntimeError(f"Claude API error: {e}")


def convert_ai_scenario_to_story(content: EducationalContent, scenario_data: dict) -> TwineStory:
    """Convert AI-generated scenario data into a TwineStory object."""

    grading_config = GradingConfig(
        enabled=True,
        concept_points={c.name: c.points for c in content.key_concepts},
        passing_threshold=content.passing_threshold,
        total_points=content.total_points,
        passing_points=content.passing_points
    )

    story = TwineStory(title=f"EdQuest: {content.theme}", grading=grading_config)

    # Introduction - keep it brief
    intro = scenario_data.get('introduction', {})
    concepts_text = "\n".join(f"- {c.name} ({c.points} pts)" for c in content.key_concepts)

    intro_content = f"""<div class="chapter-header">
<h2>{content.theme}</h2>
</div>

{intro.get('situation', 'You are about to face a series of professional decisions.')}

**Your Role:** {intro.get('role', 'Decision-maker in this scenario')}

**Stakes:** {intro.get('stakes', 'Your choices will be evaluated.')}

<div class="scenario-context">
**Concepts assessed:**
{concepts_text}

**Total Points:** {content.total_points} | **Passing:** {content.passing_threshold}%
</div>"""

    story.add_passage(Passage(
        name="Start",
        content=intro_content,
        choices=[Choice("Begin", "Chapter 1")],
        position_y=100
    ))

    # Generate passages for each chapter (concept)
    chapters = scenario_data.get('chapters', [])
    y_pos = 250

    for chapter_idx, chapter in enumerate(chapters):
        concept_num = chapter_idx + 1
        concept_name = chapter.get('concept', f'Concept {concept_num}')
        chapter_title = chapter.get('title', concept_name)

        # Find points for this concept
        points = content.default_points
        for c in content.key_concepts:
            if c.name.lower() == concept_name.lower():
                points = c.points
                break

        is_final_chapter = (chapter_idx == len(chapters) - 1)
        next_chapter = f"Chapter {concept_num + 1}" if not is_final_chapter else "Results"

        # Chapter setup - brief
        setup_text = chapter.get('setup', 'A new situation requires your decision.')
        setup_content = f"""<div class="chapter-header">
<span class="chapter-num">Chapter {concept_num}: {concept_name}</span>
<h2>{chapter_title}</h2>
</div>

{setup_text}"""

        story.add_passage(Passage(
            name=f"Chapter {concept_num}",
            content=setup_content,
            choices=[Choice("Continue", f"C{concept_num}D1")],
            position_y=y_pos
        ))
        y_pos += 120

        # Process decisions
        decisions = chapter.get('decisions', [])
        num_decisions = len(decisions)

        for dec_idx, decision in enumerate(decisions):
            dec_num = dec_idx + 1
            is_final_decision = (dec_idx == num_decisions - 1)

            situation = decision.get('situation', 'You must make a choice.')
            prompt = decision.get('prompt', 'What do you do?')

            # Decision passage - concise
            decision_content = f"""{situation}

<div class="decision-prompt">{prompt}</div>"""

            choices = decision.get('choices', [])
            passage_choices = []

            # Sort choices by quality
            best_choice = None
            partial_choice = None
            poor_choices = []

            for choice in choices:
                quality = choice.get('quality', 'poor')
                if quality == 'best':
                    best_choice = choice
                elif quality == 'partial':
                    partial_choice = choice
                else:
                    poor_choices.append(choice)

            # Ensure we have at least one of each
            if not best_choice and choices:
                best_choice = choices[0]
            if not poor_choices and len(choices) > 1:
                poor_choices = choices[1:] if not partial_choice else choices[2:]

            # Create randomized order for choices (so best isn't always first)
            all_choices = []
            if best_choice:
                all_choices.append(('best', best_choice))
            if partial_choice:
                all_choices.append(('partial', partial_choice))
            for i, pc in enumerate(poor_choices):
                all_choices.append((f'poor{i}', pc))

            # Build passage choices
            for quality_key, choice in all_choices:
                choice_text = choice.get('text', 'Take action')[:60]

                if is_final_decision:
                    # Final decision goes to outcome passages
                    if quality_key == 'best':
                        target = f"C{concept_num}Best"
                    elif quality_key == 'partial':
                        target = f"C{concept_num}Partial"
                    else:
                        target = f"C{concept_num}Poor{quality_key[-1] if quality_key[-1].isdigit() else '0'}"
                else:
                    # Intermediate decision - all paths continue
                    if quality_key == 'best':
                        target = f"C{concept_num}D{dec_num}Best"
                    elif quality_key == 'partial':
                        target = f"C{concept_num}D{dec_num}Partial"
                    else:
                        target = f"C{concept_num}D{dec_num}Poor"

                passage_choices.append(Choice(choice_text, target))

            story.add_passage(Passage(
                name=f"C{concept_num}D{dec_num}",
                content=decision_content,
                choices=passage_choices,
                position_y=y_pos
            ))
            y_pos += 100

            # Create consequence passages
            if not is_final_decision:
                next_decision = f"C{concept_num}D{dec_num + 1}"

                # Best path consequence
                if best_choice:
                    consequence = best_choice.get('consequence', 'Good outcome.')
                    story.add_passage(Passage(
                        name=f"C{concept_num}D{dec_num}Best",
                        content=f"""<div class="feedback-correct">{consequence}</div>""",
                        choices=[Choice("Continue", next_decision)],
                        position_y=y_pos
                    ))
                    y_pos += 80

                # Partial path
                if partial_choice:
                    consequence = partial_choice.get('consequence', 'Mixed results.')
                    story.add_passage(Passage(
                        name=f"C{concept_num}D{dec_num}Partial",
                        content=f"""<div class="feedback-partial">{consequence}</div>""",
                        choices=[Choice("Continue", next_decision)],
                        position_y=y_pos
                    ))
                    y_pos += 80

                # Poor path (consolidated)
                if poor_choices:
                    consequence = poor_choices[0].get('consequence', 'This creates issues.')
                    story.add_passage(Passage(
                        name=f"C{concept_num}D{dec_num}Poor",
                        content=f"""<div class="feedback-incorrect">{consequence}</div>""",
                        choices=[Choice("Continue", next_decision)],
                        position_y=y_pos
                    ))
                    y_pos += 80

            else:
                # Final decision - create outcome passages with points
                resolution = chapter.get('resolution', '')

                # Best outcome
                if best_choice:
                    feedback = best_choice.get('feedback', 'Correct application of the concept.')
                    consequence = best_choice.get('consequence', 'Success.')
                    story.add_passage(Passage(
                        name=f"C{concept_num}Best",
                        content=f"""<div class="feedback-correct">
<strong>Well done!</strong> <span class="points-earned">+{points} points</span>
</div>

{consequence}

<div class="source-reference"><strong>Why this works:</strong> {feedback}</div>

{resolution}""",
                        choices=[Choice("Continue", next_chapter)],
                        tags=["correct", f"concept-{concept_num}"],
                        position_y=y_pos
                    ))
                    y_pos += 120

                # Partial outcome
                if partial_choice:
                    partial_pts = points // 2
                    feedback = partial_choice.get('feedback', 'Partially correct.')
                    consequence = partial_choice.get('consequence', 'Mixed results.')
                    better = best_choice.get('feedback', '') if best_choice else ''
                    story.add_passage(Passage(
                        name=f"C{concept_num}Partial",
                        content=f"""<div class="feedback-partial">
<strong>Partially correct.</strong> <span class="points-partial">+{partial_pts} points</span>
</div>

{consequence}

<div class="source-reference"><strong>What was missing:</strong> {feedback}</div>
{f'<div class="source-reference"><strong>Better approach:</strong> {better[:150]}</div>' if better else ''}

{resolution}""",
                        choices=[Choice("Continue", next_chapter)],
                        tags=["partial", f"concept-{concept_num}"],
                        position_y=y_pos
                    ))
                    y_pos += 120

                # Poor outcomes
                for i, poor in enumerate(poor_choices[:2]):
                    feedback = poor.get('feedback', 'This approach has issues.')
                    consequence = poor.get('consequence', 'Problems occurred.')
                    better = best_choice.get('feedback', '') if best_choice else ''
                    story.add_passage(Passage(
                        name=f"C{concept_num}Poor{i}",
                        content=f"""<div class="feedback-incorrect">
<strong>Not quite right.</strong> <span class="points-missed">0 points</span>
</div>

{consequence}

<div class="source-reference"><strong>Issue:</strong> {feedback}</div>
{f'<div class="source-reference"><strong>Better approach:</strong> {better[:150]}</div>' if better else ''}

{resolution}""",
                        choices=[Choice("Continue", next_chapter)],
                        tags=["incorrect", f"concept-{concept_num}"],
                        position_y=y_pos
                    ))
                    y_pos += 120

    # Results passage
    conclusion = scenario_data.get('conclusion', {})
    results_content = f"""<div class="chapter-header">
<h2>Results</h2>
</div>

{{RESULTS_BOX}}

{conclusion.get('high_score', 'Great job applying these concepts!')}"""

    story.add_passage(Passage(
        name="Results",
        content=results_content,
        choices=[Choice("Try Again", "Start")],
        tags=["ending", "results"],
        position_y=y_pos
    ))

    return story


def generate_educational_scenario(content: EducationalContent, api_key: str = None,
                                   decision_nodes: int = 4, branches_per_node: int = 3,
                                   case_study_mode: bool = False, case_study: dict = None) -> TwineStory:
    """
    Generate an educational scenario, using AI if available.
    Falls back to template-based generation if AI is not available or fails.
    """
    if api_key and ANTHROPIC_AVAILABLE:
        try:
            scenario_data = generate_scenario_with_ai(
                content, api_key,
                decision_nodes=decision_nodes,
                branches_per_node=branches_per_node,
                case_study_mode=case_study_mode,
                case_study=case_study
            )
            return convert_ai_scenario_to_story(content, scenario_data)
        except Exception as e:
            print(f"AI generation failed, falling back to template: {e}")

    return generate_template_scenario(content, decision_nodes, branches_per_node)


def generate_template_scenario(content: EducationalContent,
                                decision_nodes: int = 4, branches_per_node: int = 3) -> TwineStory:
    """
    Generate a template-based educational scenario (fallback when AI unavailable).
    """
    grading_config = GradingConfig(
        enabled=True,
        concept_points={c.name: c.points for c in content.key_concepts},
        passing_threshold=content.passing_threshold,
        total_points=content.total_points,
        passing_points=content.passing_points
    )

    story = TwineStory(title=f"EdQuest: {content.theme}", grading=grading_config)
    theme_context = get_theme_context(content.theme)

    # Build introduction
    objectives_text = "\n".join(f"- {obj}" for obj in content.learning_objectives)
    concepts_text = "\n".join(f"- {c.name} ({c.points} pts)" for c in content.key_concepts)

    intro_content = f"""<div class="chapter-header">
<span class="chapter-num">Welcome</span>
<h2>{content.theme}</h2>
</div>

<div class="theme-atmosphere">
{theme_context['atmosphere']}
</div>

You find yourself {theme_context['setting']}. As {theme_context['role']}, you must navigate complex situations that will test your knowledge and decision-making abilities.

**Learning Objectives:**
{objectives_text}

**You will be assessed on:**
{concepts_text}

**Total Points:** {content.total_points} | **Passing Score:** {content.passing_threshold}%

<div class="source-reference">
<strong>Important:</strong> The correct answers require understanding and applying what you learned from the source materials.
</div>"""

    story.add_passage(Passage(
        name="Start",
        content=intro_content,
        choices=[Choice("Begin the scenario", "Scenario 1")],
        position_y=100
    ))

    # Generate scenario for each concept
    y_pos = 250
    num_concepts = len(content.key_concepts)

    for i, concept_obj in enumerate(content.key_concepts):
        concept = concept_obj.name
        points = concept_obj.points
        scenario_num = i + 1
        is_final = (i == num_concepts - 1)
        next_scenario = f"Scenario {scenario_num + 1}" if not is_final else "Results"

        npc = theme_context['npcs'][i % len(theme_context['npcs'])]

        scenario_content = f"""<div class="chapter-header">
<span class="chapter-num">Chapter {scenario_num}</span>
<h2>{concept}</h2>
</div>

<div class="theme-atmosphere">
{theme_context['atmosphere']}
</div>

<div class="scenario-context">
You encounter a situation that requires your understanding of **{concept}**. The {npc} approaches you with a challenging problem.
</div>

<div class="character-dialogue">
<span class="character-name">{npc}:</span> "We have a situation that requires your expertise. Based on what you know about {concept}, how should we proceed?"
</div>

<div class="decision-prompt">
What is the best course of action?
</div>"""

        story.add_passage(Passage(
            name=f"Scenario {scenario_num}",
            content=scenario_content,
            choices=[
                Choice(f"Apply established {concept} principles", f"Correct {scenario_num}"),
                Choice("Take a simplified approach", f"Incorrect {scenario_num}a"),
                Choice("Defer the decision", f"Incorrect {scenario_num}b"),
            ],
            position_y=y_pos
        ))
        y_pos += 150

        correct_content = f"""<div class="feedback-correct">
<strong>Excellent choice!</strong> <span class="points-earned">+{points} points</span>
</div>

Your approach correctly applies the principles of **{concept}** as outlined in the source material.

<div class="source-reference">
<strong>From the source material:</strong> This demonstrates proper application of {concept} principles.
</div>"""

        story.add_passage(Passage(
            name=f"Correct {scenario_num}",
            content=correct_content,
            choices=[Choice("Continue", next_scenario)],
            tags=["correct", f"concept-{scenario_num}"],
            position_y=y_pos
        ))
        y_pos += 150

        for suffix in ['a', 'b']:
            incorrect_content = f"""<div class="feedback-incorrect">
<strong>This approach has issues.</strong> <span class="points-missed">0 points</span>
</div>

This choice doesn't align with the proper application of **{concept}** principles from the source material.

<div class="source-reference">
<strong>Review:</strong> The source material explains the correct approach to {concept}.
</div>"""

            story.add_passage(Passage(
                name=f"Incorrect {scenario_num}{suffix}",
                content=incorrect_content,
                choices=[
                    Choice("Try again", f"Scenario {scenario_num}"),
                    Choice("Continue", next_scenario)
                ],
                tags=["incorrect", f"concept-{scenario_num}"],
                position_y=y_pos
            ))
            y_pos += 150

    results_content = f"""<div class="chapter-header">
<span class="chapter-num">Complete</span>
<h2>{content.theme}</h2>
</div>

{{RESULTS_BOX}}

Thank you for completing this assessment. Your score reflects your ability to apply the course concepts."""

    story.add_passage(Passage(
        name="Results",
        content=results_content,
        choices=[Choice("Start Again", "Start")],
        tags=["ending", "results"],
        position_y=y_pos
    ))

    return story


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Generate deep branching Twine educational scenarios.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input_file", nargs="?", help="JSON file with educational content")
    parser.add_argument("-o", "--output", help="Output HTML filename")
    parser.add_argument("--demo", action="store_true", help="Generate demo scenario")
    parser.add_argument("--api-key", help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")

    args = parser.parse_args()

    api_key = args.api_key or os.environ.get('ANTHROPIC_API_KEY')

    if args.demo or not args.input_file:
        print("Demo mode - creating sample scenario...")
        content = EducationalContent(
            theme="Healthcare/Clinical Setting",
            learning_objectives=[
                "Apply diagnostic criteria to identify patient conditions",
                "Evaluate treatment options based on evidence"
            ],
            key_concepts=[
                ConceptWithPoints("Differential Diagnosis", 25),
                ConceptWithPoints("Treatment Planning", 25),
                ConceptWithPoints("Patient Communication", 25),
                ConceptWithPoints("Ethical Decision Making", 25)
            ],
            source_content="Medical ethics requires informed consent from all patients...",
            passing_threshold=70
        )
        output_file = args.output or "demo_scenario.html"
    else:
        content = EducationalContent.from_json_file(args.input_file)
        output_file = args.output or Path(args.input_file).stem + "_scenario.html"

    story = generate_educational_scenario(content, api_key)
    html_content = story.generate_html()

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Generated: {output_file}")
    return 0


if __name__ == "__main__":
    exit(main())

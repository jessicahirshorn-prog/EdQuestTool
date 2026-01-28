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
import random
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
    background: linear-gradient(135deg, #003366 0%, #004488 100%);
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
    background: linear-gradient(135deg, #003366 0%, #004488 100%);
    color: #FFD700;
    text-decoration: none;
    border-radius: 8px;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
    font-weight: 600;
    white-space: normal;
    word-wrap: break-word;
    overflow-wrap: break-word;
    line-height: 1.4;
    border: 2px solid #FFD700;
}}
tw-link:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(255, 215, 0, 0.4);
    background: #FFD700;
    color: #003366;
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
    border-left: 4px solid #003366;
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
    background: linear-gradient(135deg, #fff9e6 0%, #fff3cc 100%);
    border-left: 4px solid #FFD700;
    padding: 14px 16px;
    margin: 16px 0;
    border-radius: 0 8px 8px 0;
    font-style: italic;
    color: #003366;
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
    color: #003366;
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
    background: linear-gradient(135deg, #003366 0%, #004488 100%);
    color: #FFD700;
    padding: 16px 20px;
    margin: -32px -32px 24px -32px;
    border-radius: 16px 16px 0 0;
    border-bottom: 3px solid #FFD700;
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

    function getConceptFromPassage(passageName, passageTags) {
        const concepts = Object.keys(grading.config.conceptPoints || {});
        const tags = passageTags || [];

        // NEW BRANCHING TREE: Check tags for concept and score info
        // Tags format: ["correct", "concept-1", "score-100"] or ["partial", "concept-2", "score-50"]
        let conceptNum = null;
        let scorePercent = null;
        let isCorrect = false;
        let isPartial = false;

        for (const tag of tags) {
            if (tag.startsWith('concept-')) {
                conceptNum = parseInt(tag.replace('concept-', ''));
            } else if (tag.startsWith('score-')) {
                scorePercent = parseInt(tag.replace('score-', ''));
            } else if (tag === 'correct') {
                isCorrect = true;
            } else if (tag === 'partial') {
                isPartial = true;
            }
        }

        // If we found concept info from tags, use it
        if (conceptNum !== null && conceptNum <= concepts.length) {
            // For branching scenarios, use score percentage to determine points
            if (scorePercent !== null) {
                return {
                    concept: concepts[conceptNum - 1],
                    isCorrect: scorePercent >= 80,
                    isPartial: scorePercent >= 40 && scorePercent < 80,
                    scorePercent: scorePercent
                };
            }
            return {
                concept: concepts[conceptNum - 1],
                isCorrect: isCorrect,
                isPartial: isPartial,
                scorePercent: isCorrect ? 100 : (isPartial ? 50 : 0)
            };
        }

        // LEGACY: Match patterns like "C1Best", "C1Partial", "C1Poor0" (old AI-generated scenarios)
        const aiMatch = passageName.match(/^C(\\d+)(Best|Partial|Poor\\d*)$/);
        if (aiMatch) {
            const num = parseInt(aiMatch[1]);
            const quality = aiMatch[2];
            if (num <= concepts.length) {
                return {
                    concept: concepts[num - 1],
                    isCorrect: quality === 'Best',
                    isPartial: quality === 'Partial',
                    scorePercent: quality === 'Best' ? 100 : (quality === 'Partial' ? 50 : 0)
                };
            }
        }

        // LEGACY: Match patterns like "Correct 1", "Incorrect 2a", "Partial 1b" (template scenarios)
        const templateMatch = passageName.match(/(Correct|Incorrect|Partial)\\s+(\\d+)/);
        if (templateMatch) {
            const num = parseInt(templateMatch[2]);
            if (num <= concepts.length) {
                return {
                    concept: concepts[num - 1],
                    isCorrect: templateMatch[1] === 'Correct',
                    isPartial: templateMatch[1] === 'Partial',
                    scorePercent: templateMatch[1] === 'Correct' ? 100 : (templateMatch[1] === 'Partial' ? 50 : 0)
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
            // Pass passage tags to enable branching tree scoring
            const conceptInfo = getConceptFromPassage(name, passage.tags);
            if (conceptInfo && grading.conceptResults[conceptInfo.concept]) {
                const result = grading.conceptResults[conceptInfo.concept];
                result.attempts++;
                if (!result.answered) {
                    // Use scorePercent for branching scenarios, fallback to binary correct/partial
                    if (conceptInfo.scorePercent !== undefined && conceptInfo.scorePercent !== null) {
                        // Calculate earned points based on score percentage
                        result.earned = Math.floor(result.points * conceptInfo.scorePercent / 100);
                        result.correct = conceptInfo.scorePercent >= 80;
                        result.answered = true;
                        grading.score += result.earned;
                        updateScoreDisplay();
                    } else if (conceptInfo.isCorrect) {
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
                    } else {
                        // Poor/incorrect ending - 0 points but mark as answered
                        result.answered = true;
                        result.earned = 0;
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

        // For Results page, content already has HTML structure - don't wrap in <p> tags
        if (name !== 'Results') {
            content = content.split('\\n\\n').map(p => '<p>' + p.replace(/\\n/g, '<br>') + '</p>').join('');
        }

        // Add navigation buttons (except on Start)
        let navButtons = '';
        if (name === 'Results') {
            // Special "Play Again" button for results page
            navButtons = '<div class="nav-buttons" style="justify-content: center;">';
            navButtons += '<button class="nav-btn" style="background: linear-gradient(135deg, #003366 0%, #004488 100%); color: #FFD700; padding: 14px 28px; font-size: 1.1rem; border: 2px solid #FFD700; font-weight: 600;" onclick="resetScenario()">Play Again</button>';
            navButtons += '</div>';
        } else if (name !== 'Start') {
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

        // Collect concepts by performance
        const masteredConcepts = [];
        const partialConcepts = [];
        const needsReviewConcepts = [];

        let conceptBreakdown = '';
        for (const [concept, result] of Object.entries(grading.conceptResults)) {
            let cls = result.correct ? 'correct' : (result.earned > 0 ? 'partial' : 'incorrect');
            let icon = result.correct ? '\\u2713' : (result.earned > 0 ? '~' : '\\u2717');
            let pts = result.earned > 0 ? '+' + result.earned : '0';
            conceptBreakdown += '<div class="concept-result ' + cls + '"><span>' + icon + ' ' + concept + '</span><span>' + pts + ' / ' + result.points + ' pts</span></div>';

            if (result.correct) {
                masteredConcepts.push(concept);
            } else if (result.earned > 0) {
                partialConcepts.push(concept);
            } else {
                needsReviewConcepts.push(concept);
            }
        }

        // Build detailed performance explanation
        let performanceExplanation = '<div style="margin-top:20px; padding:16px; background:white; border-radius:8px;">';
        performanceExplanation += '<h3 style="margin:0 0 12px 0; color:#003366; font-size:1.1rem;">Performance Analysis</h3>';

        if (masteredConcepts.length > 0) {
            performanceExplanation += '<div style="margin-bottom:12px;"><strong style="color:#059669;">Concepts Mastered:</strong> ';
            performanceExplanation += 'You demonstrated strong understanding of <em>' + masteredConcepts.join('</em>, <em>') + '</em>. ';
            performanceExplanation += 'Your decisions showed you can correctly apply ' + (masteredConcepts.length === 1 ? 'this concept' : 'these concepts') + ' in realistic scenarios.</div>';
        }

        if (partialConcepts.length > 0) {
            performanceExplanation += '<div style="margin-bottom:12px;"><strong style="color:#d97706;">Partial Understanding:</strong> ';
            performanceExplanation += 'You showed some understanding of <em>' + partialConcepts.join('</em>, <em>') + '</em>, but your approach was incomplete. ';
            performanceExplanation += 'Review the nuances of ' + (partialConcepts.length === 1 ? 'this concept' : 'these concepts') + ' to strengthen your application skills.</div>';
        }

        if (needsReviewConcepts.length > 0) {
            performanceExplanation += '<div style="margin-bottom:12px;"><strong style="color:#dc2626;">Needs Review:</strong> ';
            performanceExplanation += 'The concepts of <em>' + needsReviewConcepts.join('</em>, <em>') + '</em> require additional study. ';
            performanceExplanation += 'Focus on understanding how ' + (needsReviewConcepts.length === 1 ? 'this concept applies' : 'these concepts apply') + ' to real-world situations.</div>';
        }

        // Overall recommendation
        if (passed) {
            performanceExplanation += '<div style="margin-top:12px; padding:12px; background:#d1fae5; border-radius:6px; color:#065f46;">';
            performanceExplanation += '<strong>Overall:</strong> You have demonstrated proficiency in applying these concepts. ';
            if (partialConcepts.length > 0 || needsReviewConcepts.length > 0) {
                performanceExplanation += 'To achieve mastery, continue practicing the areas noted above.';
            } else {
                performanceExplanation += 'Excellent work across all assessed areas!';
            }
            performanceExplanation += '</div>';
        } else {
            performanceExplanation += '<div style="margin-top:12px; padding:12px; background:#fee2e2; border-radius:6px; color:#991b1b;">';
            performanceExplanation += '<strong>Recommendation:</strong> Review the source materials focusing on the concepts marked for review. ';
            performanceExplanation += 'Pay attention to how these concepts are applied in practice, then try the scenario again.';
            performanceExplanation += '</div>';
        }

        performanceExplanation += '</div>';

        return '<div class="results-box ' + statusClass + '">' +
            '<div class="results-score">' + percentage + '%</div>' +
            '<div class="results-status">' + statusText + '</div>' +
            '<div><strong>Score:</strong> ' + grading.score + ' / ' + grading.config.totalPoints + ' points</div>' +
            '<div><strong>Required:</strong> ' + grading.config.passingThreshold + '%</div>' +
            '<div style="margin-top:16px"><strong>Concept Breakdown:</strong></div>' +
            conceptBreakdown +
            performanceExplanation + '</div>';
    }

    function generateResultsContent() {
        return '<div class="chapter-header"><h2>Your Results</h2></div>' + generateResultsBox();
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
                               case_study_mode: bool = False, case_study: dict = None,
                               custom_scenario_description: str = None) -> dict:
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

    # Prepare custom scenario description if provided
    custom_scenario_section = ""
    if custom_scenario_description:
        custom_scenario_section = f"""
## CUSTOM SCENARIO DESCRIPTION (PRIMARY SOURCE - BUILD SCENARIO AROUND THIS)

{custom_scenario_description}

CRITICAL: The scenario MUST be built around this custom description. Use the specific:
- Setting, location, and environment described
- Characters, roles, and relationships mentioned
- Situation, context, and circumstances outlined
- Any specific details the instructor provided
The student should experience EXACTLY the scenario described above. Do NOT substitute generic elements.
"""

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

    # Calculate branching depth based on decision_nodes
    # With true branching, we need a tree structure
    # depth 1 = root decision, depth 2 = second level, etc.
    branching_depth = min(decision_nodes, 3)  # Cap at 3 levels to keep content manageable

    prompt = f"""You are creating a TRUE BRANCHING NARRATIVE educational scenario. This is NOT a linear quiz - student choices must lead to GENUINELY DIFFERENT paths and outcomes.

## CRITICAL: TRUE BRANCHING STRUCTURE

This scenario must be a BRANCHING TREE, not a linear sequence:
- Each choice leads to a DIFFERENT situation (not the same next question)
- Different paths have DIFFERENT events, challenges, and outcomes
- Poor early choices should lead to increasingly difficult situations
- Good early choices should open up better opportunities
- The narrative should DIVERGE based on choices, not converge

Example of WRONG (linear) structure:
  Decision 1 → [all paths] → Decision 2 → [all paths] → Decision 3 → End

Example of CORRECT (branching) structure:
  Decision 1
  ├── Choice A → Situation A → Decision 2A → [branches to different endings]
  ├── Choice B → Situation B → Decision 2B → [branches to different endings]
  └── Choice C → Situation C → Decision 2C → [branches to different endings]

## DESIGN PRINCIPLES

### 1. MEANINGFUL BRANCHING
- Each choice should lead to a narratively DIFFERENT situation
- If you choose to confront someone vs. avoid them, the next scene should be COMPLETELY DIFFERENT
- Choices have CONSEQUENCES that shape the rest of the story
- Students should feel their choices MATTER

### 2. ALL CHOICES MUST SOUND REASONABLE
- Every choice should sound like something a thoughtful professional might consider
- Wrong choices reflect common misconceptions, not obvious mistakes
- A student who hasn't studied should find all options equally plausible
- NO choices like "ignore the problem" or "do nothing"

### 3. CONSEQUENCES SNOWBALL
- Early optimal choices → easier subsequent situations → better endings
- Early poor choices → harder subsequent situations → worse endings
- But EVERY path should be interesting and educational

### 4. MULTIPLE ENDINGS
- Each concept should have {branches_per_node} to {branches_per_node * 2} possible endings
- Endings vary from "excellent application" (full points) to "needs review" (minimal points)
- Each ending should explain what the student's path demonstrated

## Theme: {content.theme}
- Setting: {theme_context['setting']}
- Student Role: {theme_context['role']}
- Stakes: {theme_context['stakes']}
{custom_scenario_section}{case_study_section}
## SUPPLEMENTARY MATERIALS
{source_text if source_text else "(No additional materials provided)"}

## Learning Objectives
{objectives_list}

## Key Concepts to Assess
{concepts_list}

## BRANCHING STRUCTURE REQUIREMENTS

Create {len(content.key_concepts)} chapters, one per concept. Each chapter is a BRANCHING TREE:
- Depth: {branching_depth} levels of decisions
- Branches: {branches_per_node} choices at each decision point
- Each branch leads to a UNIQUE next situation
- Multiple endings per chapter (ranging from optimal to poor outcomes)

## JSON OUTPUT FORMAT - BRANCHING TREE STRUCTURE

Return ONLY valid JSON with this TREE structure:

{{
  "introduction": {{
    "opening_narrative": "1-2 paragraphs immersing the student in the scenario. Vivid setting, clear role, atmospheric.",
    "role": "Student's specific role",
    "stakes": "What's at stake"
  }},
  "chapters": [
    {{
      "concept": "Concept name being tested",
      "title": "Chapter title",
      "setup": "Brief transition to this chapter's situation",
      "branch_tree": {{
        "root": {{
          "node_id": "root",
          "situation": "2-3 sentences describing the situation the student faces",
          "choices": [
            {{
              "text": "Action description (max 60 chars)",
              "quality": "optimal",
              "leads_to": "node_a",
              "transition": "1-2 sentences describing immediate consequence and transition"
            }},
            {{
              "text": "Action description (max 60 chars)",
              "quality": "adequate",
              "leads_to": "node_b",
              "transition": "1-2 sentences describing immediate consequence and transition"
            }},
            {{
              "text": "Action description (max 60 chars)",
              "quality": "poor",
              "leads_to": "node_c",
              "transition": "1-2 sentences describing immediate consequence and transition"
            }}
          ]
        }},
        "node_a": {{
          "node_id": "node_a",
          "situation": "NEW situation resulting from optimal choice - different from node_b and node_c",
          "choices": [
            {{
              "text": "Action (max 60 chars)",
              "quality": "optimal",
              "leads_to": "ending_excellent",
              "transition": "Consequence leading to ending"
            }},
            {{
              "text": "Action (max 60 chars)",
              "quality": "adequate",
              "leads_to": "ending_good",
              "transition": "Consequence leading to ending"
            }},
            {{
              "text": "Action (max 60 chars)",
              "quality": "poor",
              "leads_to": "ending_mixed_a",
              "transition": "Consequence leading to ending"
            }}
          ]
        }},
        "node_b": {{
          "node_id": "node_b",
          "situation": "DIFFERENT situation resulting from adequate choice",
          "choices": [
            {{
              "text": "Action (max 60 chars)",
              "quality": "optimal",
              "leads_to": "ending_good",
              "transition": "Consequence"
            }},
            {{
              "text": "Action (max 60 chars)",
              "quality": "adequate",
              "leads_to": "ending_mixed_b",
              "transition": "Consequence"
            }},
            {{
              "text": "Action (max 60 chars)",
              "quality": "poor",
              "leads_to": "ending_poor",
              "transition": "Consequence"
            }}
          ]
        }},
        "node_c": {{
          "node_id": "node_c",
          "situation": "DIFFICULT situation resulting from poor initial choice",
          "choices": [
            {{
              "text": "Recovery action (max 60 chars)",
              "quality": "optimal",
              "leads_to": "ending_mixed_c",
              "transition": "Partial recovery"
            }},
            {{
              "text": "Action (max 60 chars)",
              "quality": "adequate",
              "leads_to": "ending_poor",
              "transition": "Consequence"
            }},
            {{
              "text": "Action (max 60 chars)",
              "quality": "poor",
              "leads_to": "ending_fail",
              "transition": "Consequence"
            }}
          ]
        }},
        "ending_excellent": {{
          "node_id": "ending_excellent",
          "is_ending": true,
          "score_percent": 100,
          "title": "Excellent Outcome",
          "narrative": "2-3 sentences describing the successful outcome",
          "feedback": "Explanation of why this path demonstrated mastery of the concept",
          "concept_demonstrated": "How the student showed understanding"
        }},
        "ending_good": {{
          "node_id": "ending_good",
          "is_ending": true,
          "score_percent": 80,
          "title": "Good Outcome",
          "narrative": "Outcome description",
          "feedback": "What went well and what could improve",
          "concept_demonstrated": "Partial application shown"
        }},
        "ending_mixed_a": {{
          "node_id": "ending_mixed_a",
          "is_ending": true,
          "score_percent": 60,
          "title": "Mixed Results",
          "narrative": "Outcome with some issues",
          "feedback": "Analysis of the path taken",
          "concept_demonstrated": "Gaps in application"
        }},
        "ending_mixed_b": {{
          "node_id": "ending_mixed_b",
          "is_ending": true,
          "score_percent": 50,
          "title": "Partial Success",
          "narrative": "Outcome description",
          "feedback": "What was missing",
          "concept_demonstrated": "Limited demonstration"
        }},
        "ending_mixed_c": {{
          "node_id": "ending_mixed_c",
          "is_ending": true,
          "score_percent": 40,
          "title": "Recovery",
          "narrative": "Recovered from poor start",
          "feedback": "Good recovery but early mistake cost points",
          "concept_demonstrated": "Eventually showed understanding"
        }},
        "ending_poor": {{
          "node_id": "ending_poor",
          "is_ending": true,
          "score_percent": 25,
          "title": "Needs Improvement",
          "narrative": "Problematic outcome",
          "feedback": "Key concepts were not properly applied",
          "concept_demonstrated": "Review needed"
        }},
        "ending_fail": {{
          "node_id": "ending_fail",
          "is_ending": true,
          "score_percent": 0,
          "title": "Unsuccessful",
          "narrative": "Poor outcome requiring review",
          "feedback": "The approach taken did not apply the concept correctly",
          "concept_demonstrated": "Concept review strongly recommended"
        }}
      }}
    }}
  ],
  "conclusion": {{
    "high_score": "Congratulations message",
    "medium_score": "Encouragement message",
    "low_score": "Review suggestion"
  }}
}}

## CRITICAL REQUIREMENTS

1. Each node_id must be UNIQUE within the chapter
2. Every "leads_to" must reference an existing node_id
3. Decision nodes have "choices" array; ending nodes have "is_ending": true
4. Situations in different branches must be NARRATIVELY DIFFERENT
5. All choice text must be professional-sounding (max 60 chars)
6. Endings should range from 100% (excellent) to 0% (needs review)
7. Create {branches_per_node * 2} to {branches_per_node * 3} unique endings per concept
8. The tree must have {branching_depth} levels of decisions before reaching endings

Return ONLY valid JSON."""

    # DEBUG: Log the prompt being sent to Claude
    print("\n" + "="*60)
    print("DEBUG: Prompt being sent to Claude AI")
    print("="*60)
    print(f"Custom Scenario Section Present: {'Yes' if custom_scenario_section else 'No'}")
    print(f"Case Study Section Present: {'Yes' if case_study_section else 'No'}")
    if custom_scenario_section:
        print("\n--- CUSTOM SCENARIO SECTION CONTENT ---")
        print(custom_scenario_section[:500])
        print("--- END PREVIEW ---\n")
    print("="*60 + "\n")

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
    """Convert AI-generated branching scenario data into a TwineStory object.

    Handles the new branching tree structure where each choice leads to
    genuinely different paths and outcomes.
    """

    grading_config = GradingConfig(
        enabled=True,
        concept_points={c.name: c.points for c in content.key_concepts},
        passing_threshold=content.passing_threshold,
        total_points=content.total_points,
        passing_points=content.passing_points
    )

    story = TwineStory(title=f"EdQuest: {content.theme}", grading=grading_config)

    # Introduction - immersive opening
    intro = scenario_data.get('introduction', {})
    concepts_text = "\n".join(f"- {c.name} ({c.points} pts)" for c in content.key_concepts)

    # Use opening_narrative if available, fall back to situation for backwards compatibility
    opening_text = intro.get('opening_narrative', intro.get('situation', 'You are about to face a branching narrative.'))

    intro_content = f"""<div class="chapter-header">
<h2>{content.theme}</h2>
</div>

{opening_text}

<div class="scenario-context">
**Your Role:** {intro.get('role', 'Decision-maker in this scenario')}

**Stakes:** {intro.get('stakes', 'Your choices will be evaluated.')}
</div>

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

    # Generate passages for each chapter (concept) using BRANCHING TREE structure
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
            choices=[Choice("Continue", f"C{concept_num}_root")],
            position_y=y_pos
        ))
        y_pos += 120

        # Check if this chapter uses the new branching tree structure
        branch_tree = chapter.get('branch_tree', None)

        if branch_tree:
            # NEW BRANCHING TREE STRUCTURE
            # Process each node in the branch tree
            for node_id, node in branch_tree.items():
                passage_name = f"C{concept_num}_{node_id}"

                if node.get('is_ending', False):
                    # This is an ending node - award points based on score_percent
                    score_percent = node.get('score_percent', 0)
                    earned_points = int(points * score_percent / 100)
                    title = node.get('title', 'Outcome')
                    narrative = node.get('narrative', 'The scenario concludes.')
                    feedback = node.get('feedback', '')
                    concept_demo = node.get('concept_demonstrated', '')

                    # Determine feedback style based on score
                    if score_percent >= 80:
                        feedback_class = "feedback-correct"
                        points_class = "points-earned"
                        status = "Excellent!"
                    elif score_percent >= 50:
                        feedback_class = "feedback-partial"
                        points_class = "points-partial"
                        status = "Good effort."
                    else:
                        feedback_class = "feedback-incorrect"
                        points_class = "points-missed"
                        status = "Needs review."

                    ending_content = f"""<div class="chapter-header">
<h2>{title}</h2>
</div>

<div class="{feedback_class}">
<strong>{status}</strong> <span class="{points_class}">+{earned_points} points ({score_percent}%)</span>
</div>

{narrative}

<div class="source-reference"><strong>Assessment:</strong> {feedback}</div>
<div class="source-reference"><strong>Concept Application:</strong> {concept_demo}</div>"""

                    # Determine tags based on score for grading system
                    if score_percent >= 80:
                        tags = ["correct", f"concept-{concept_num}", f"score-{score_percent}"]
                    elif score_percent >= 50:
                        tags = ["partial", f"concept-{concept_num}", f"score-{score_percent}"]
                    else:
                        tags = ["incorrect", f"concept-{concept_num}", f"score-{score_percent}"]

                    story.add_passage(Passage(
                        name=passage_name,
                        content=ending_content,
                        choices=[Choice("Continue", next_chapter)],
                        tags=tags,
                        position_y=y_pos
                    ))
                    y_pos += 120

                else:
                    # This is a decision node - create choices that branch
                    situation = node.get('situation', 'You face a decision.')
                    choices_data = node.get('choices', [])

                    decision_content = f"""{situation}

<div class="decision-prompt">What do you do?</div>"""

                    # Build passage choices - shuffle to randomize position
                    passage_choices = []
                    choices_list = list(choices_data)
                    random.shuffle(choices_list)

                    for choice in choices_list:
                        choice_text = choice.get('text', 'Take action')[:60]
                        leads_to = choice.get('leads_to', 'root')
                        target = f"C{concept_num}_{leads_to}"
                        transition = choice.get('transition', '')

                        # Store transition text for display after choice
                        passage_choices.append(Choice(choice_text, f"{target}_trans" if transition else target))

                        # Create transition passage if there's transition text
                        if transition:
                            quality = choice.get('quality', 'adequate')
                            if quality == 'optimal':
                                trans_class = "feedback-correct"
                            elif quality == 'adequate':
                                trans_class = "feedback-partial"
                            else:
                                trans_class = "feedback-incorrect"

                            story.add_passage(Passage(
                                name=f"{target}_trans",
                                content=f"""<div class="{trans_class}">{transition}</div>""",
                                choices=[Choice("Continue", target)],
                                position_y=y_pos
                            ))
                            y_pos += 60

                    story.add_passage(Passage(
                        name=passage_name,
                        content=decision_content,
                        choices=passage_choices,
                        position_y=y_pos
                    ))
                    y_pos += 100

        else:
            # FALLBACK: Old linear structure for backwards compatibility
            decisions = chapter.get('decisions', [])
            num_decisions = len(decisions)

            for dec_idx, decision in enumerate(decisions):
                dec_num = dec_idx + 1
                is_final_decision = (dec_idx == num_decisions - 1)

                situation = decision.get('situation', 'You must make a choice.')
                prompt = decision.get('prompt', 'What do you do?')

                decision_content = f"""{situation}

<div class="decision-prompt">{prompt}</div>"""

                choices = decision.get('choices', [])
                passage_choices = []

                best_choice = None
                partial_choice = None
                poor_choices = []

                for choice in choices:
                    quality = choice.get('quality', 'poor')
                    if quality in ['best', 'optimal']:
                        best_choice = choice
                    elif quality in ['partial', 'adequate']:
                        partial_choice = choice
                    else:
                        poor_choices.append(choice)

                if not best_choice and choices:
                    best_choice = choices[0]
                if not poor_choices and len(choices) > 1:
                    poor_choices = choices[1:] if not partial_choice else choices[2:]

                all_choices = []
                if best_choice:
                    all_choices.append(('best', best_choice))
                if partial_choice:
                    all_choices.append(('partial', partial_choice))
                for i, pc in enumerate(poor_choices):
                    all_choices.append((f'poor{i}', pc))

                random.shuffle(all_choices)

                for quality_key, choice in all_choices:
                    choice_text = choice.get('text', 'Take action')[:60]

                    if is_final_decision:
                        if quality_key == 'best':
                            target = f"C{concept_num}Best"
                        elif quality_key == 'partial':
                            target = f"C{concept_num}Partial"
                        else:
                            target = f"C{concept_num}Poor{quality_key[-1] if quality_key[-1].isdigit() else '0'}"
                    else:
                        if quality_key == 'best':
                            target = f"C{concept_num}D{dec_num}Best"
                        elif quality_key == 'partial':
                            target = f"C{concept_num}D{dec_num}Partial"
                        else:
                            target = f"C{concept_num}D{dec_num}Poor"

                    passage_choices.append(Choice(choice_text, target))

                # For backwards compatibility, use C{n}_root for first decision
                passage_name = f"C{concept_num}_root" if dec_num == 1 else f"C{concept_num}D{dec_num}"

                story.add_passage(Passage(
                    name=passage_name,
                    content=decision_content,
                    choices=passage_choices,
                    position_y=y_pos
                ))
                y_pos += 100

                if not is_final_decision:
                    next_decision = f"C{concept_num}D{dec_num + 1}"

                    if best_choice:
                        consequence = best_choice.get('consequence', 'Good outcome.')
                        story.add_passage(Passage(
                            name=f"C{concept_num}D{dec_num}Best",
                            content=f"""<div class="feedback-correct">{consequence}</div>""",
                            choices=[Choice("Continue", next_decision)],
                            position_y=y_pos
                        ))
                        y_pos += 80

                    if partial_choice:
                        consequence = partial_choice.get('consequence', 'Mixed results.')
                        story.add_passage(Passage(
                            name=f"C{concept_num}D{dec_num}Partial",
                            content=f"""<div class="feedback-partial">{consequence}</div>""",
                            choices=[Choice("Continue", next_decision)],
                            position_y=y_pos
                        ))
                        y_pos += 80

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
                    resolution = chapter.get('resolution', '')

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
                                   case_study_mode: bool = False, case_study: dict = None,
                                   custom_scenario_description: str = None) -> TwineStory:
    """
    Generate an educational scenario, using AI if available.
    Falls back to template-based generation if AI is not available or fails.
    """
    print(f"[EdQuest] generate_educational_scenario called")
    print(f"[EdQuest] api_key provided: {bool(api_key)}, length: {len(api_key) if api_key else 0}")
    print(f"[EdQuest] ANTHROPIC_AVAILABLE: {ANTHROPIC_AVAILABLE}")

    if api_key and ANTHROPIC_AVAILABLE:
        print("[EdQuest] Attempting AI generation...")
        try:
            scenario_data = generate_scenario_with_ai(
                content, api_key,
                decision_nodes=decision_nodes,
                branches_per_node=branches_per_node,
                case_study_mode=case_study_mode,
                case_study=case_study,
                custom_scenario_description=custom_scenario_description
            )
            print("[EdQuest] AI generation successful!")
            return convert_ai_scenario_to_story(content, scenario_data)
        except Exception as e:
            import traceback
            print(f"[EdQuest] AI generation failed: {type(e).__name__}: {e}")
            traceback.print_exc()
            print("[EdQuest] Falling back to template...")
    else:
        print(f"[EdQuest] Skipping AI - api_key: {bool(api_key)}, ANTHROPIC_AVAILABLE: {ANTHROPIC_AVAILABLE}")

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

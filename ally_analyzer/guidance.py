"""Deliver the shipped Claude skills to hosts without native skill invocation."""
import hashlib
from pathlib import Path

from . import __version__
from .util import AnalyzerError

SKILLS = ('explain', 'analyze', 'investigate', 'review', 'write-report')


def get_session_guide(skill='explain'):
    if skill not in SKILLS:
        raise AnalyzerError('Unknown session guide')
    path = Path(__file__).resolve().parent.parent / 'skills' / skill / 'SKILL.md'
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise AnalyzerError('Bundled skill is unavailable in this installation. Use the complete Claude plugin archive.') from exc
    return {'skill': 'ally-session-analyzer:' + skill, 'plugin_version': __version__,
            'relative_path': 'skills/' + skill + '/SKILL.md', 'sha256': hashlib.sha256(content).hexdigest(),
            'instructions': content.decode('utf-8'), 'origin': 'bundled_plugin_instructions_not_session_content'}

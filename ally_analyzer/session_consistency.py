"""Version-bound semantic review requirements, not deterministic entailment.

Claude performs these checks. Code checks their presence, internal status and
revision dependencies, and reports literal writing signals without rewriting.
"""
import re
from .util import AnalyzerError

VERSION = 'semantic-consistency-v2'
GENERIC_EXPLANATIONS = {'error text', 'denial message', 'tool result', 'error message',
                        'source evidence', 'supporting evidence', 'this supports the analysis',
                        'this supports the claim', 'this is relevant evidence'}
COMMON = ('specific_citation_explanations', 'decision_relevant_limits')
ASPECTS = {
    'requirement_map': ('obligation_separation', 'completion_evidence', *COMMON),
    'conclusion_draft': ('opening_requirement_consistency', 'distinct_field_purposes', *COMMON),
    'incident': ('status_qualification_consistency', *COMMON),
    'failure_explanation': ('status_qualification_consistency', *COMMON),
    'inquiry': COMMON,
    'recommendation': ('status_qualification_consistency', *COMMON),
}
GUIDANCE = {
    'obligation_separation': 'First establish what the instruction requires. Do not turn sentence order or a preferred workflow into a mandatory prerequisite. Preserve plausible competing readings in intent_interpretation; if they change the outcome, leave it unverified. Then separate material obligations whose outcomes differ; do not approve a completed bundle acknowledging a missed explicit instruction. Do not split duplicate or immaterial intent into checklist filler.',
    'completion_evidence': 'Compare each status and its basis with primary evidence, missing evidence, verification scope and revision. A passed functional test does not prove a requested procedural step was followed.',
    'opening_requirement_consistency': 'Compare title, synopsis and outcome with every material status and intent_interpretation in the CURRENT requirement map. Preserve an unmet explicit obligation even when implementation passes. An unresolved interpretation must not become a confident process failure in the opening. Keep task completion separate from investigation completeness and freshness. Bind related_record_ids to the current map.',
    'distinct_field_purposes': 'Synopsis identifies intent and work; outcome states supported completion and remaining work; detailed reasoning explains why. Remove repeated chronology and checklist-like titles.',
    'specific_citation_explanations': 'Each reader-facing citation explains what this record establishes about THIS claim. Its explanation is the visible source-link label. Filenames, Error text, Denial message and vague approval are not explanations. Check the actual action/result and any material limit against the inspected range; a command shows an attempt, not success. Repair through a saved revision, never renderer rewriting.',
    'status_qualification_consistency': 'Expectedness, resolution, diagnosis, title and prose must agree. Inspect reader_guide takeaway and every local event against its decisive record, anchor turn, episode and chronology. A launch is not a result; later recovery is not another failure. Different goals need separate episodes, and a local uncertainty cannot become a whole-pattern defect. Expected needs evidence of intentional negative checking or correct policy enforcement. Benign, common and recovered do not mean expected. A caveat cannot repair an incorrect confident label; revise it or preserve a needs_revision judgment.',
    'decision_relevant_limits': 'Name the actual missing evidence beside the affected claim. Remove repeated generic cautions; retain uncertainty that changes the decision. Review any next_action against current unmet intent and results; its verification must settle the stated gap. Do not prescribe redoing recovered work or turn an immediate check into a persistent instruction.',
}


def generic_explanation(text):
    return re.sub(r'[.!:\s]+$', '', text.strip().casefold()) in GENERIC_EXPLANATIONS


def citation_flags(value, path=()):
    flags = []
    if isinstance(value, dict):
        if 'source_id' in value and not value.get('explanation','').strip():
            flags.append({'code':'missing_source_explanation', 'path':'.'.join(path), 'source_id':value['source_id']})
        if 'source_id' in value and generic_explanation(value.get('explanation', '')):
            flags.append({'code':'generic_source_explanation', 'path':'.'.join(path), 'source_id':value['source_id'], 'saved_text':value['explanation']})
        for key, child in value.items(): flags += citation_flags(child, path+(key,))
    elif isinstance(value, list):
        for i, child in enumerate(value): flags += citation_flags(child, path+(str(i),))
    return flags


def writing_signals(value, kind):
    signals = citation_flags(value)
    if kind == 'conclusion_draft':
        fields = {'synopsis':value.get('synopsis',{}).get('text',''),
                  'outcome':value.get('observed_outcome',{}).get('text',''), 'summary':value.get('summary','')}
        sentences = {}
        for field, text in fields.items():
            for sentence in re.split(r'(?<=[.!?])\s+', text.strip()):
                if len(sentence.split()) >= 6: sentences.setdefault(sentence, set()).add(field)
        signals += [{'code':'repeated_opening_sentence','fields':sorted(fields),'saved_text':text}
                    for text, fields in sentences.items() if len(fields)>1]
    return signals


def review_plan(kind, value, map_id=None):
    return {'required_aspects':list(ASPECTS[kind]), 'guidance':{key:GUIDANCE[key] for key in ASPECTS[kind]},
            'current_requirement_map_id':map_id if kind=='conclusion_draft' else None,
            'literal_writing_signals':writing_signals(value,kind),
            'limitation':'Literal repetition and generic labels are review signals. Semantic consistency remains a Claude judgment, not a quality certificate.'}


def validate_semantic_check(check, kind, active_ids, map_id):
    entries=check.get('semantic_checks',[])
    by_aspect={entry['aspect']:entry for entry in entries}
    if len(by_aspect)!=len(entries): raise AnalyzerError('Semantic check aspects must be unique')
    missing=set(ASPECTS[kind])-by_aspect.keys()
    if missing: raise AnalyzerError('Review the required semantic aspects: '+', '.join(sorted(missing)))
    for entry in entries:
        if set(entry['related_record_ids'])-active_ids:
            raise AnalyzerError('Semantic checks must refer to current records, not superseded revisions')
        if check['verdict']!='needs_revision' and entry['verdict']=='needs_revision':
            raise AnalyzerError('A semantic contradiction requires needs_revision; a qualification cannot approve it')
    if kind=='conclusion_draft':
        entry=by_aspect['opening_requirement_consistency']
        if map_id and map_id not in entry['related_record_ids']:
            raise AnalyzerError('Bind the opening consistency check to the current requirement map ID')
        if map_id and entry['verdict']=='not_applicable':
            raise AnalyzerError('Opening consistency is applicable when a requirement map exists')


def stale_dependencies(check, active_ids):
    return sorted({rid for c in check.get('semantic_checks',[]) for rid in c['related_record_ids'] if rid not in active_ids})

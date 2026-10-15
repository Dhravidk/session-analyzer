"""Inspect exact proposed text without applying it or rewriting model output."""
import hashlib
import re
from pathlib import Path
from .session_scope import get_scope, source_record
from .util import AnalyzerError, digest

INSTRUCTION_TARGETS = ('use_existing_skill', 'existing_skill', 'new_skill', 'claude_md')


def validate_edit_shape(edit):
    operation = edit['operation']
    if operation == 'invoke':
        if not edit.get('invocation', '').strip() or any(k in edit for k in ('original_text','replacement_text')):
            raise AnalyzerError('An invocation requires only invocation text, not replacement fields')
    else:
        if 'replacement_text' not in edit or 'invocation' in edit:
            raise AnalyzerError('A text edit needs replacement_text and no invocation')
        if operation == 'create':
            if edit.get('original_text') or not edit['replacement_text']:
                raise AnalyzerError('Create needs nonempty complete content and no original text')
        elif not edit.get('original_text'):
            raise AnalyzerError('Replacement/insertion needs exact nonempty original_text as its unique location')


def inspect_edit(store, run, proposal):
    edit = proposal.get('edit')
    if not edit:
        return {'status':'not_supplied', 'reason':'No exact edit or invocation was saved.', 'net_growth':None}
    validate_edit_shape(edit)
    target_id = proposal.get('target_snapshot_id')
    if edit['operation'] == 'create':
        path = Path(edit['target_path']).expanduser()
        if path.is_absolute():
            identity = digest(str(path.resolve()))
            snapshots = [source_record(store,run,aid)['metadata'] for aid in get_scope(store,run)['artifact_ids']]
            if any(s['temporal_relation']=='current' and s['origin_path_hash']==identity for s in snapshots):
                return {'status':'needs_evidence','reason':'The create path matches an existing current snapshot. Propose a narrow edit to that file instead.','net_growth':None}
        before, after = '', edit['replacement_text']
        match = True; reason = 'New file content; absence and appropriate scope remain part of instruction review.'
    elif not target_id:
        return {'status':'needs_evidence', 'reason':'Current target snapshot is missing.', 'net_growth':None}
    else:
        source = source_record(store, run, target_id)
        if source['kind'] != 'artifact':
            return {'status':'needs_evidence','reason':'Target must be an admitted artifact.', 'net_growth':None}
        before = source['record']['message']['content']
        if edit['operation'] == 'invoke':
            name = re.search(r'^name:\s*[\'\"]?([^\n\'\"]+)', before, re.M)
            command = edit['invocation'].split()[0]
            match = bool(name and command.startswith('/') and (command == '/' + name.group(1).strip() or command.endswith(':' + name.group(1).strip())))
            return {'status':'matched' if match else 'needs_evidence', 'reason':'Invocation matches the captured skill name.' if match else 'Invocation does not match a captured skill name; installation and invocation availability are not established.',
                    'net_growth':{'bytes':0,'words':0,'lines':0,'basis':'Invocation does not propose a file edit.'} if match else None}
        original = edit['original_text']; match = before.count(original) == 1
        reason = 'Exact original text occurs once in the selected snapshot.' if match else 'Original text is absent or ambiguous in the selected snapshot.'
        if not match:
            return {'status':'needs_evidence', 'reason':reason, 'net_growth':None}
        replacement = edit['replacement_text']
        if edit['operation'] == 'insert_before': replacement += original
        if edit['operation'] == 'insert_after': replacement = original + replacement
        after = before.replace(original, replacement, 1)
    candidate_id = proposal.get('candidate_snapshot_id')
    candidate_matches = None
    if candidate_id:
        candidate_matches = source_record(store, run, candidate_id)['record']['message']['content'] == after
    return {'status':'matched' if match and candidate_matches is not False else 'needs_evidence', 'reason':reason,
            'candidate_matches_exact_edit':candidate_matches, 'proposed_content_sha256':hashlib.sha256(after.encode()).hexdigest(),
            'net_growth':{'bytes':len(after.encode()) - len(before.encode()), 'words':len(after.split()) - len(before.split()),
                          'lines':len(after.splitlines()) - len(before.splitlines()),
                          'basis':'Exact proposed text applied in memory to the selected snapshot; words are whitespace-separated, bytes are UTF-8. No file was modified.'}}

"""Describe captured content without confusing empty, withheld and unknown text.

Thinking text is available only in explicitly requested local source exports.
It is not added to the investigator's versioned evidence-text projection.
"""
import hashlib
import re

from .investigation import REDACTIONS

VERSION = 'source-content-v1'
MEDIA = {'image', 'audio', 'video', 'document', 'base64'}
OMIT_FIELDS = {'env','environment','env_vars','thinking','signature','base64','image','audio','video'}


def masked_text(text):
    for pattern, replacement in REDACTIONS:
        text = re.sub(pattern, replacement, text)
    return text


def source_content(record, include_thinking_text=False):
    items, thinking, omissions = [], [], []

    def nested_omissions(value,path):
        if isinstance(value,list):
            for i,item in enumerate(value):nested_omissions(item,path+'['+str(i)+']')
        elif isinstance(value,dict):
            kind=value.get('type')
            if isinstance(kind,str) and kind in MEDIA | {'thinking','redacted_thinking'}:
                omissions.append({'path':path,'type':kind,'reason':('The provider-redacted thinking payload cannot be displayed as readable text.' if kind=='redacted_thinking' else 'The nested '+kind+' payload is deliberately excluded from the text projection.')})
                return
            for key,item in value.items():
                if key.lower() in OMIT_FIELDS:
                    omissions.append({'path':path+'.'+masked_text(key),'type':key.lower(),'reason':'The '+key.lower()+' field is deliberately excluded from the text projection.'})
                else:nested_omissions(item,path+'.'+masked_text(key))

    def add(path, kind, status, reason, **extra):
        items.append(dict(path=path, type=kind, status=status, reason=reason, **extra))

    def visit(content, path, present=True):
        if not present or content is None:
            add(path, 'content', 'missing', 'No content value was captured at '+path+'.')
        elif isinstance(content, str):
            add(path, 'text', 'available' if content.strip() else 'empty',
                'Captured text is available.' if content.strip() else 'The captured text is empty.', characters=len(content))
        elif not isinstance(content, list):
            add(path, 'content', 'unsupported', 'The captured content format is unsupported: '+type(content).__name__+'.')
        elif not content:
            add(path, 'content', 'empty', 'The captured content array is empty.')
        else:
            for index, block in enumerate(content):
                at = path+'['+str(index)+']'
                if not isinstance(block, dict):
                    add(at, 'content', 'unsupported', 'The captured block is not an object: '+type(block).__name__+'.')
                    continue
                kind = block.get('type')
                if kind == 'thinking':
                    value = block.get('thinking')
                    if isinstance(value, str) and value.strip():
                        add(at, kind, 'omitted_by_policy', 'Thinking text is retained in the log but excluded from the analyzer evidence projection.', characters=len(value))
                        if include_thinking_text:
                            text = masked_text(value)
                            thinking.append({'path':at, 'text':text, 'text_sha256':hashlib.sha256(text.encode()).hexdigest(),
                                             'usage_scope':'local_source_export_only', 'evidence_projection':False})
                    elif isinstance(value, str):
                        add(at, kind, 'empty', 'The captured thinking field is empty; no readable thinking text was recorded.', characters=len(value))
                    elif value is None:
                        add(at, kind, 'missing', 'The thinking block has no captured thinking text field.')
                    else:
                        add(at, kind, 'unsupported', 'The thinking field has an unsupported format: '+type(value).__name__+'.')
                elif kind == 'redacted_thinking':
                    add(at, kind, 'provider_redacted', 'The provider redacted this thinking block; no readable thinking text is available.')
                elif isinstance(kind, str) and kind in MEDIA:
                    add(at, kind, 'omitted_by_policy', 'The '+kind+' payload is deliberately excluded from the text-only source projection.')
                elif kind == 'text':
                    if isinstance(block.get('text'), str):
                        visit(block['text'], at+'.text')
                    else:
                        value=block.get('text')
                        add(at, kind, 'missing' if value is None else 'unsupported',
                            'The text block has no captured text field.' if value is None else 'The text field has an unsupported format: '+type(value).__name__+'.')
                elif kind == 'tool_result':
                    visit(block.get('content'), at+'.content', 'content' in block)
                elif kind == 'tool_use':
                    add(at, kind, 'available', 'The captured tool invocation is available.')
                    if 'input' in block:nested_omissions(block['input'],at+'.input')
                else:
                    name = masked_text(str(kind))[:160] if kind is not None else '(type absent)'
                    add(at, name, 'unsupported', 'Unsupported captured block type: '+name+'.')

    message = record.get('message')
    container, path = (message, 'message.content') if isinstance(message, dict) else (record, 'content')
    visit(container.get('content'), path, 'content' in container)
    for field in ('attachment','data','error','errorMessage','failureReason','exitReason','status'):
        if isinstance(record.get(field),(dict,list)):nested_omissions(record[field],field)
    if 'environment' in record:
        omissions.append({'path':'environment','type':'environment','reason':'The top-level environment payload is deliberately excluded from the text projection.'})
    types = {item['type'] for item in items}
    has_thinking = bool(types & {'thinking', 'redacted_thinking'})
    kind = 'thinking' if has_thinking and types <= {'thinking', 'redacted_thinking'} else 'mixed' if has_thinking else 'other'
    return {'version':VERSION, 'kind':kind, 'has_visible_text':any(b['type']=='text' and b['status']=='available' for b in items),
            'blocks':items, 'projection_omissions':omissions, 'thinking_text':thinking,
            'thinking_text_exported':bool(thinking), 'thinking_is_execution_evidence':False}


def assistant_role(record):
    """Tool/status roles are decided by the caller before this fallback."""
    info = source_content(record)
    if info['kind'] == 'thinking':
        return 'assistant_thinking'
    if any(b['type'] == 'text' and b['status'] == 'available' for b in info['blocks']):
        return 'assistant_statement'
    return 'assistant_record'

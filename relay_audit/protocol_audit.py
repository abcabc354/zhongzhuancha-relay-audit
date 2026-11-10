#!/usr/bin/env python3
"""中转查 · 协议面审计：模拟 Codex/Responses 客户端，检查协议契约。

不认证型号身份；只回答“这个中转是否像一个忠实的 Codex/Responses 直连”。
参考 AIO Coding Hub 的 Claude 验证器思路：官方客户端仿真 + roundtrip + 参数契约。
"""
import argparse
import base64
import json
import os
import stat
import struct
import sys
import time
import zlib
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .evidence import (  # noqa: E402
    ContractError, digest, object_hash, save, stamp, verify_manifest, write_manifest)

SCHEMA = 'gpt-protocol-audit-v1'
DEFAULT_MODEL = 'gpt-6.1-sol'
LIMITS = {'requests': 28, 'request_seconds': 120, 'batch_seconds': 900,
          'output_per_request': 2500}
KEY_NAMES = ('OPENAI_API_KEY', 'RELAY_CHECK_API_KEY', 'API_KEY')
BASE_NAMES = ('OPENAI_BASE_URL', 'RELAY_CHECK_BASE_URL', 'BASE_URL')
REASON = ('1 이상 60 이하의 정수 a, b에 대해 a×b가 완전제곱수가 되는 순서쌍 (a,b)의 개수를 구하세요. '
          '마지막 줄에 `ANSWER: <정수>` 형식으로만 답하세요.')
CAP = 'Count from 1 to 100, one number per line.'
EXTRACT = ('从这句话中抽取城市和日期，只输出 JSON，键为 city 和 date，'
           '日期用 YYYY-MM-DD：「我们定在2026年3月14日去杭州开会。」')
TOOL = {'type': 'function', 'name': 'lookup_inventory',
        'description': 'Look up the stock count for one SKU.',
        'parameters': {'type': 'object', 'properties': {'sku': {'type': 'string'}},
                       'required': ['sku'], 'additionalProperties': False},
        'strict': True}
CITY_SCHEMA = {'type': 'object',
               'properties': {'city': {'type': 'string'}, 'date': {'type': 'string'}},
               'required': ['city', 'date'], 'additionalProperties': False}
SUITE = ('models', 'responses_min', 'effort_low', 'effort_high', 'prev_roundtrip',
         'invalid_effort', 'image', 'cap', 'chat', 'catalog_liveness',
         'usage_repeat', 'cross_model')


def png_red(size=64):
    raw = b''.join(b'\x00' + bytes((220, 20, 20)) * size for _ in range(size))

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))

    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw))
            + chunk(b'IEND', b''))


def summarize(completed):
    if not completed:
        return {'present': False}
    usage = completed.get('usage') or {}
    details = usage.get('output_tokens_details') or {}
    inputs = usage.get('input_tokens_details') or {}
    output = completed.get('output') or []
    texts = []
    for item in output:
        for part in item.get('content') or []:
            if part.get('type') == 'output_text':
                texts.append(part.get('text') or '')
    instructions = completed.get('instructions') or ''
    return {
        'present': True,
        'id': completed.get('id'),
        'object': completed.get('object'),
        'status': completed.get('status'),
        'model': completed.get('model'),
        'system_fingerprint': completed.get('system_fingerprint'),
        'service_tier': completed.get('service_tier'),
        'access_programs': completed.get('access_programs'),
        'output_types': [item.get('type') for item in output],
        'phases': [item.get('phase') for item in output if item.get('phase')],
        'text': ''.join(texts),
        'usage': {'input_tokens': usage.get('input_tokens'),
                  'output_tokens': usage.get('output_tokens'),
                  'reasoning_tokens': details.get('reasoning_tokens'),
                  'cached_tokens': inputs.get('cached_tokens'),
                  'attribution_present': isinstance(usage.get('attribution'), dict)},
        'reasoning': completed.get('reasoning'),
        'text_config': completed.get('text'),
        'store': completed.get('store'),
        'prompt_cache_retention': completed.get('prompt_cache_retention'),
        'tool_calls': [{'type': item.get('type'), 'name': item.get('name'),
                        'arguments': item.get('arguments')}
                       for item in output if item.get('type') in ('function_call', 'tool_call')],
        'prompt_cache_key': completed.get('prompt_cache_key'),
        'instructions_len': len(instructions),
        'instructions_sha256': digest(instructions.encode()) if instructions else None,
        'instructions_head': instructions[:200],
        'instructions_has_codex': 'Codex' in instructions,
        'instructions_has_gpt5': 'GPT-5' in instructions,
    }


def post_stream(client, path, body, secret, timeout=240, auth=True):
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True).encode()
    started = time.monotonic()
    status = None
    headers = {}
    try:
        headers = {'Content-Type': 'application/json'}
        if auth:
            headers['Authorization'] = 'Bearer ' + secret
        with client.stream('POST', path, content=raw, headers=headers) as response:
            status = response.status_code
            headers = {k: v for k, v in response.headers.items()
                       if k.lower() in ('content-type', 'x-request-id')}
            data = b''.join(response.iter_bytes())
    except Exception as error:  # noqa: BLE001
        return {'status': None, 'error': type(error).__name__ + ': ' + str(error)[:200],
                'duration_s': round(time.monotonic() - started, 1), 'completed': None,
                'raw_bytes': 0, 'raw_excerpt': ''}
    completed = None
    failure = None
    text = data.decode('utf-8', 'replace')
    for line in text.splitlines():
        if not line.startswith('data:'):
            continue
        payload = line[5:].strip()
        if not payload or payload == '[DONE]':
            continue
        try:
            event = json.loads(payload)
        except ValueError:
            continue
        if event.get('type') == 'response.completed':
            completed = event.get('response') or event
        elif event.get('type') == 'response.failed':
            failure = event.get('response') or event
    error = None
    if status is not None and status != 200:
        try:
            parsed = json.loads(text)
            error = parsed.get('error') or parsed
        except ValueError:
            error = text[:300]
    return {'status': status, 'headers': headers, 'error': error,
            'duration_s': round(time.monotonic() - started, 1), 'completed': completed,
            'failure': failure, 'raw_bytes': len(data), 'raw_excerpt': text[:300]}


def post_json(client, path, body, secret, timeout=120, auth=True):
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True).encode()
    started = time.monotonic()
    try:
        headers = {'Content-Type': 'application/json'}
        if auth:
            headers['Authorization'] = 'Bearer ' + secret
        response = client.post(path, content=raw, headers=headers)
        parsed = None
        try:
            parsed = response.json()
        except ValueError:
            parsed = None
        return {'status': response.status_code, 'json': parsed,
                'duration_s': round(time.monotonic() - started, 1),
                'raw_bytes': len(response.content)}
    except Exception as error:  # noqa: BLE001
        return {'status': None, 'error': type(error).__name__ + ': ' + str(error)[:200],
                'duration_s': round(time.monotonic() - started, 1)}


def response_body(model, prompt, *, effort=None, max_tokens=2500, store=False,
                  previous=None, input_value=None):
    body = {'model': model, 'input': input_value if input_value is not None else prompt,
            'max_output_tokens': max_tokens, 'store': store, 'stream': True}
    if effort:
        body['reasoning'] = {'effort': effort}
    if previous:
        body['previous_response_id'] = previous
    return body


def catalog_ids(models, exclude=()):
    blocked = {item for item in exclude if isinstance(item, str)}
    return [item for item in models
            if isinstance(item, str) and item.startswith('gpt-') and item not in blocked][:5]


def catalog_selection(model, models, mode='target', exclude=()):
    if mode == 'target':
        return [model]
    return catalog_ids(models, exclude)


def responses_available(result):
    return result.get('status') == 200 and (result.get('summary') or {}).get('present')


def post_chat_stream(client, body, secret, timeout=240):
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True).encode()
    started = time.monotonic()
    status = None
    try:
        with client.stream('POST', '/chat/completions', content=raw,
                           headers={'Authorization': 'Bearer ' + secret,
                                    'Content-Type': 'application/json'}) as response:
            status = response.status_code
            data = b''.join(response.iter_bytes())
    except Exception as error:  # noqa: BLE001
        return {'status': None, 'error': type(error).__name__ + ': ' + str(error)[:200],
                'duration_s': round(time.monotonic() - started, 1),
                'text': '', 'usage': None, 'finish_reason': None, 'raw_excerpt': ''}
    text = ''
    finish = None
    usage = None
    error = None
    body_text = data.decode('utf-8', 'replace')
    for line in body_text.splitlines():
        if not line.startswith('data:'):
            continue
        payload = line[5:].strip()
        if payload == '[DONE]':
            break
        try:
            event = json.loads(payload)
        except ValueError:
            continue
        if isinstance(event.get('usage'), dict):
            usage = event['usage']
        for choice in event.get('choices') or []:
            delta = choice.get('delta') or {}
            if delta.get('content'):
                text += delta['content']
            if choice.get('finish_reason'):
                finish = choice['finish_reason']
        if event.get('error'):
            error = event['error']
    if status != 200:
        try:
            parsed = json.loads(body_text)
            error = parsed.get('error') or parsed
        except ValueError:
            error = body_text[:300]
    return {'status': status, 'text': text, 'finish_reason': finish,
            'usage': usage, 'error': error,
            'duration_s': round(time.monotonic() - started, 1),
            'raw_excerpt': body_text[:300]}


def run_chat_suite(client, secret, model, models, exclude=(), catalog_mode='target'):
    basic = {'model': model, 'messages': [{'role': 'user', 'content': 'hi'}],
             'max_completion_tokens': 16, 'temperature': 0}
    out = {'chat': post_json(client, '/chat/completions', basic, secret)}
    out['chat_stream'] = post_chat_stream(client, {**basic, 'stream': True,
                                                  'stream_options': {'include_usage': True}}, secret)
    tool = {'type': 'function',
            'function': {'name': 'lookup_inventory',
                         'description': 'Look up the stock count for one SKU.',
                         'parameters': {'type': 'object',
                                        'properties': {'sku': {'type': 'string'}},
                                        'required': ['sku'],
                                        'additionalProperties': False}}}
    out['chat_tools'] = post_json(client, '/chat/completions', {
        'model': model,
        'messages': [{'role': 'user',
                      'content': 'Look up the stock for SKU B7. Use the lookup_inventory tool.'}],
        'tools': [tool],
        'tool_choice': {'type': 'function', 'function': {'name': 'lookup_inventory'}},
        'max_completion_tokens': 128, 'temperature': 0}, secret)
    out['chat_structured'] = post_json(client, '/chat/completions', {
        'model': model,
        'messages': [{'role': 'user', 'content': EXTRACT}],
        'response_format': {'type': 'json_schema',
                            'json_schema': {'name': 'city_date', 'strict': True,
                                            'schema': CITY_SCHEMA}},
        'max_completion_tokens': 128, 'temperature': 0}, secret)
    out['chat_vision'] = post_json(client, '/chat/completions', {
        'model': model,
        'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': 'What color is this image? Answer one word.'},
            {'type': 'image_url',
             'image_url': {'url': 'data:image/png;base64,'
                                  + base64.b64encode(png_red()).decode()}}]}],
        'max_completion_tokens': 32, 'temperature': 0}, secret)
    out['usage_repeat'] = [post_json(client, '/chat/completions', basic, secret)
                           for _ in range(2)]
    ids = catalog_selection(model, models, catalog_mode, exclude)
    out['catalog_liveness'] = {
        item: post_json(client, '/chat/completions',
                        {'model': item, 'messages': [{'role': 'user', 'content': 'hi'}],
                         'max_completion_tokens': 8, 'temperature': 0}, secret).get('status')
        for item in ids}
    return out


def run_suite(client, secret, model, exclude=(), catalog_mode='target', mode='auto'):
    started_asia = stamp()
    started = time.monotonic()
    out = {}

    try:
        response = client.get('/models', headers={'Authorization': 'Bearer ' + secret})
        result = {'status': response.status_code}
        try:
            payload = response.json()
            result['models'] = [item.get('id') for item in (payload.get('data') or [])
                                if isinstance(item, dict)]
        except ValueError:
            result['models'] = []
        out['catalog'] = result
    except Exception as error:  # noqa: BLE001
        out['catalog'] = {'status': None, 'error': type(error).__name__ + ': ' + str(error)[:200]}
    models = out['catalog'].get('models') or []

    if mode == 'chat':
        out['responses_min'] = {'status': None, 'error': 'forced_chat_mode',
                                'summary': {'present': False}}
        out.update(run_chat_suite(client, secret, model, models, exclude, catalog_mode))
        out['_meta'] = {'mode': 'chat', 'started_asia': started_asia, 'ended_asia': stamp(),
                        'duration_s': round(time.monotonic() - started, 1),
                        'requests': 8 + len(out['catalog_liveness'])}
        return out

    out['responses_min'] = post_stream(client, '/responses',
                                       response_body(model, 'hi', max_tokens=16), secret)
    out['responses_min']['summary'] = summarize(out['responses_min']['completed'])

    if mode == 'auto' and not responses_available(out['responses_min']):
        out.update(run_chat_suite(client, secret, model, models, exclude, catalog_mode))
        out['_meta'] = {'mode': 'chat', 'started_asia': started_asia, 'ended_asia': stamp(),
                        'duration_s': round(time.monotonic() - started, 1),
                        'requests': 9 + len(out['catalog_liveness'])}
        return out

    for effort in ('low', 'high'):
        key = 'effort_' + effort
        out[key] = post_stream(client, '/responses',
                               response_body(model, REASON, effort=effort, max_tokens=2500), secret)
        out[key]['summary'] = summarize(out[key]['completed'])

    first = post_stream(client, '/responses',
                        response_body(model, 'My favorite color is teal. Remember it.',
                                      max_tokens=32, store=True), secret)
    first_summary = summarize(first['completed'])
    out['prev_first'] = {**first, 'summary': first_summary}
    first_id = first_summary.get('id')
    if first_id:
        second = post_stream(client, '/responses',
                             response_body(model, 'What is my favorite color? Answer one word.',
                                           max_tokens=32, previous=first_id), secret)
        out['prev_second'] = {**second, 'summary': summarize(second['completed'])}
    else:
        out['prev_second'] = {'status': None, 'error': 'no previous response id',
                              'summary': {'present': False}}

    out['invalid_effort'] = post_stream(client, '/responses',
                                        response_body(model, 'hi', effort='none', max_tokens=16), secret)
    out['invalid_effort']['summary'] = summarize(out['invalid_effort']['completed'])

    out['invalid_model'] = post_stream(
        client, '/responses',
        response_body('gpt-6.1-sol-does-not-exist', 'hi', max_tokens=16), secret)
    out['invalid_model']['summary'] = summarize(out['invalid_model']['completed'])

    out['invalid_cap'] = post_stream(
        client, '/responses',
        response_body(model, 'hi', max_tokens=0), secret)
    out['invalid_cap']['summary'] = summarize(out['invalid_cap']['completed'])

    out['unauthorized'] = post_stream(
        client, '/responses',
        response_body(model, 'hi', max_tokens=16), secret, auth=False)
    out['unauthorized']['summary'] = summarize(out['unauthorized']['completed'])

    image_body = {'model': model, 'stream': True, 'max_output_tokens': 32, 'store': False,
                  'input': [{'role': 'user', 'content': [
                      {'type': 'input_text', 'text': 'What color is this image? Answer one word.'},
                      {'type': 'input_image',
                       'image_url': 'data:image/png;base64,'
                                    + base64.b64encode(png_red()).decode()}]}]}
    out['image'] = post_stream(client, '/responses', image_body, secret)
    out['image']['summary'] = summarize(out['image']['completed'])

    out['cap'] = post_stream(client, '/responses',
                             response_body(model, CAP, max_tokens=8), secret)
    out['cap']['summary'] = summarize(out['cap']['completed'])

    out['cache_retention'] = post_stream(
        client, '/responses',
        {'model': model, 'input': 'hi', 'max_output_tokens': 16, 'store': False,
         'stream': True, 'prompt_cache_retention': '24h'}, secret)
    out['cache_retention']['summary'] = summarize(out['cache_retention']['completed'])

    out['verbosity'] = post_stream(
        client, '/responses',
        {'model': model, 'input': 'hi', 'max_output_tokens': 32, 'store': False,
         'stream': True, 'text': {'verbosity': 'low'}}, secret)
    out['verbosity']['summary'] = summarize(out['verbosity']['completed'])

    out['tools'] = post_stream(
        client, '/responses',
        {'model': model,
         'input': 'Look up the stock for SKU B7. Use the lookup_inventory tool.',
         'max_output_tokens': 96, 'store': False, 'stream': True,
         'tools': [TOOL],
         'tool_choice': {'type': 'function', 'name': 'lookup_inventory'}}, secret)
    out['tools']['summary'] = summarize(out['tools']['completed'])

    out['structured'] = post_stream(
        client, '/responses',
        {'model': model, 'input': EXTRACT,
         'max_output_tokens': 128, 'store': False, 'stream': True,
         'text': {'format': {'type': 'json_schema', 'name': 'city_date',
                             'schema': CITY_SCHEMA, 'strict': True}}}, secret)
    out['structured']['summary'] = summarize(out['structured']['completed'])

    out['chat'] = post_json(client, '/chat/completions',
                            {'model': model, 'messages': [{'role': 'user', 'content': 'hi'}],
                             'max_completion_tokens': 16, 'temperature': 0}, secret)

    ids = catalog_selection(model, out['catalog'].get('models') or [],
                            catalog_mode, exclude)
    liveness = {}
    for item in ids:
        liveness[item] = post_json(client, '/chat/completions',
                                   {'model': item, 'messages': [{'role': 'user', 'content': 'hi'}],
                                    'max_completion_tokens': 8, 'temperature': 0}, secret).get('status')
    out['catalog_liveness'] = liveness

    repeats = []
    for _ in range(2):
        result = post_stream(client, '/responses',
                             response_body(model, 'hi', max_tokens=16), secret)
        repeats.append({**{k: v for k, v in result.items() if k != 'completed'},
                        'summary': summarize(result['completed'])})
    out['usage_repeat'] = repeats

    cross = post_stream(client, '/responses',
                        response_body('gpt-6-sol', 'hi', max_tokens=16), secret)
    out['cross_model'] = {**cross, 'summary': summarize(cross['completed'])}

    requests = 19 + len(liveness) + (1 if first_id else 0)
    out['_meta'] = {'mode': 'responses', 'started_asia': started_asia, 'ended_asia': stamp(),
                    'duration_s': round(time.monotonic() - started, 1),
                    'requests': requests}
    return out


def _chat_content(result):
    payload = result.get('json') or {}
    choices = payload.get('choices') or []
    if not choices:
        return ''
    return ((choices[0].get('message') or {}).get('content') or '')


def _assess_chat(results):
    findings = []

    def add(level, code, message, evidence=None):
        findings.append({'level': level, 'code': code, 'message': message,
                         'evidence': evidence})

    chat = results.get('chat', {})
    if chat.get('status') == 200 and isinstance(chat.get('json'), dict):
        add('pass', 'chat.surface', 'Chat Completions surface works')
    else:
        add('fail', 'chat.surface', 'Chat Completions surface failed',
            {'status': chat.get('status')})

    stream = results.get('chat_stream', {})
    if (stream.get('status') == 200 and stream.get('finish_reason')
            and (stream.get('text') or '')):
        add('pass', 'chat.stream', 'streaming completion finished with content')
    else:
        add('warn', 'chat.stream', 'streaming completion incomplete or empty',
            {'status': stream.get('status'), 'finish': stream.get('finish_reason')})

    tools = results.get('chat_tools', {})
    calls = []
    payload = tools.get('json') or {}
    choices = payload.get('choices') or []
    if choices:
        calls = (choices[0].get('message') or {}).get('tool_calls') or []
    blob = ''
    if calls:
        arguments = (calls[0].get('function') or {}).get('arguments')
        blob = arguments if isinstance(arguments, str) else json.dumps(arguments, ensure_ascii=False)
    if tools.get('status') == 200 and 'B7' in blob:
        add('pass', 'chat.tools', 'Chat function call produced with expected args')
    else:
        add('warn', 'chat.tools', 'Chat function call missing or unexpected',
            {'status': tools.get('status'), 'calls': len(calls)})

    structured = results.get('chat_structured', {})
    text = _chat_content(structured)
    ok = False
    try:
        value = json.loads(text.strip())
        ok = (isinstance(value, dict) and value.get('city') == '杭州'
              and value.get('date') == '2026-03-14')
    except ValueError:
        ok = False
    if structured.get('status') == 200 and ok:
        add('pass', 'chat.structured', 'Chat JSON schema output matched')
    else:
        add('warn', 'chat.structured', 'Chat JSON schema output missing or mismatched',
            {'status': structured.get('status'), 'text': text[:120]})

    vision = results.get('chat_vision', {})
    if vision.get('status') == 200 and 'red' in _chat_content(vision).lower():
        add('pass', 'chat.vision', 'Chat image input answered correctly')
    else:
        add('warn', 'chat.vision', 'Chat image input not answered as expected',
            {'status': vision.get('status'), 'text': _chat_content(vision)[:120]})

    values = []
    for item in results.get('usage_repeat') or []:
        usage = ((item.get('json') or {}).get('usage') or {}) if isinstance(item, dict) else {}
        value = usage.get('prompt_tokens')
        if isinstance(value, int):
            values.append(value)
    if len(values) >= 2 and min(values) > 0:
        ratio = max(values) / min(values)
        if ratio > 1.05:
            add('warn', 'usage.stability', 'same request reports different prompt_tokens',
                {'values': values, 'ratio': round(ratio, 3)})
        else:
            add('pass', 'usage.stability', 'prompt_tokens stable across repeats',
                {'values': values})
    elif results.get('usage_repeat'):
        add('warn', 'usage.stability', 'usage values unavailable')

    liveness = results.get('catalog_liveness') or {}
    failed = {model: status for model, status in liveness.items() if status != 200}
    if failed:
        add('warn', 'catalog.liveness', 'catalog lists models that fail on chat',
            {'failed': failed, 'checked': liveness})
    elif liveness:
        add('pass', 'catalog.liveness', 'all sampled catalog models answered',
            {'checked': liveness, 'failed': {}})

    add('info', 'identity.undetermined',
        'protocol surface only; model identity is not authenticated')
    fails = sum(item['level'] == 'fail' for item in findings)
    warns = sum(item['level'] == 'warn' for item in findings)
    return {'status': 'inconsistent' if fails else ('partial' if warns else 'consistent'),
            'mode': 'chat', 'findings': findings,
            'counts': {'pass': sum(item['level'] == 'pass' for item in findings),
                       'info': sum(item['level'] == 'info' for item in findings),
                       'warn': warns, 'fail': fails},
            'identity_authenticated': False, 'model_identity': 'undetermined'}


def assess(results):
    if (results.get('_meta') or {}).get('mode') == 'chat':
        return _assess_chat(results)
    findings = []

    def add(level, code, message, evidence=None):
        findings.append({'level': level, 'code': code, 'message': message,
                         'evidence': evidence})

    def shape(result):
        error = result.get('error') or {}
        if isinstance(error, dict):
            return {'status': result.get('status'), 'type': error.get('type'),
                    'param': error.get('param'), 'code': error.get('code')}
        return {'status': result.get('status'), 'raw': str(error)[:120]}

    minimum = results['responses_min']
    summary = minimum['summary']
    if minimum.get('status') != 200 or not summary.get('present'):
        add('fail', 'responses.surface', 'Responses surface unavailable')
    else:
        add('pass', 'responses.surface', 'Responses surface returned a completed response')
        if summary['usage'].get('attribution_present'):
            add('pass', 'responses.attribution', 'usage.attribution present')
        else:
            add('warn', 'responses.attribution', 'usage.attribution missing')
        if 'reasoning' in summary.get('output_types', []):
            add('pass', 'responses.reasoning_items', 'reasoning output item present')
        else:
            add('info', 'responses.reasoning_items', 'no reasoning item in this short call')
        if 'final_answer' in summary.get('phases', []):
            add('pass', 'responses.final_answer', 'message phase=final_answer')
        else:
            add('info', 'responses.final_answer', 'message phase absent')

    instructions = summary.get('instructions_len') or 0
    if instructions:
        add('info', 'wrapper.instructions',
            f'relay injects {instructions} chars of instructions',
            {'sha256': summary.get('instructions_sha256'),
             'head': summary.get('instructions_head')})
        if summary.get('instructions_has_codex') or summary.get('instructions_has_gpt5'):
            add('warn', 'wrapper.persona',
                'injected instructions declare Codex/GPT-5 persona',
                {'codex': summary.get('instructions_has_codex'),
                 'gpt5': summary.get('instructions_has_gpt5')})
    else:
        add('warn', 'wrapper.instructions', 'no instructions echoed by Responses')

    low = results.get('effort_low', {}).get('summary', {})
    high = results.get('effort_high', {}).get('summary', {})
    low_reason = (low.get('usage') or {}).get('reasoning_tokens')
    high_reason = (high.get('usage') or {}).get('reasoning_tokens')
    if isinstance(low_reason, int) and isinstance(high_reason, int):
        if high_reason > low_reason:
            add('pass', 'reasoning.scaling', 'reasoning tokens increase with effort',
                {'low': low_reason, 'high': high_reason})
        else:
            add('warn', 'reasoning.scaling', 'reasoning tokens do not increase with effort',
                {'low': low_reason, 'high': high_reason})
    else:
        add('warn', 'reasoning.scaling', 'reasoning tokens unavailable')

    second = results.get('prev_second', {})
    second_summary = second.get('summary') or {}
    text = (second_summary.get('text') or '').lower()
    if second.get('status') == 200 and 'teal' in text:
        add('pass', 'previous.roundtrip', 'previous_response_id roundtrip works')
    elif second.get('status') == 200:
        add('fail', 'previous.roundtrip',
            'previous_response_id accepted but context was lost',
            {'status': 200, 'text': text[:120]})
    elif second.get('status') == 503:
        add('warn', 'previous.roundtrip',
            'previous_response_id continuation provider temporarily unavailable',
            {'status': second.get('status'), 'error': second.get('error')})
    elif second.get('status') == 400:
        blob = json.dumps(second.get('error') or {}, ensure_ascii=False).lower()
        if any(token in blob for token in ('previous_response', 'not supported', 'unsupported')):
            add('fail', 'previous.roundtrip',
                'previous_response_id rejected as unsupported',
                {'status': second.get('status'), 'error': second.get('error')})
        else:
            add('warn', 'previous.roundtrip',
                'previous_response_id failed with 400 (upstream), not counted as a contract violation',
                {'status': second.get('status'), 'error': second.get('error')})
    else:
        add('warn', 'previous.roundtrip', 'previous_response_id roundtrip failed or lost context',
            {'status': second.get('status'), 'text': text[:120]})

    invalid = results.get('invalid_effort', {})
    error = invalid.get('error') or {}
    error_type = error.get('type') if isinstance(error, dict) else None
    if invalid.get('status') == 400 and error_type == 'invalid_request_error':
        add('pass', 'invalid.parameter', 'invalid reasoning.effort rejected as invalid_request_error')
    elif invalid.get('status') == 200:
        add('fail', 'invalid.parameter',
            'invalid reasoning.effort "none" was accepted (official gpt-6.1-sol rejects it)',
            {'status': invalid.get('status')})
    else:
        add('warn', 'invalid.parameter', 'invalid reasoning.effort not rejected in the expected shape',
            {'status': invalid.get('status'), 'error_type': error_type})

    model_shape = shape(results.get('invalid_model', {}))
    if model_shape['status'] in (400, 404) and model_shape.get('type') in (
            'invalid_request_error', 'model_not_found'):
        add('pass', 'error.invalid_model', 'invalid model rejected with an official-looking error',
            model_shape)
    elif model_shape['status'] == 200:
        add('fail', 'error.invalid_model', 'invalid model was accepted', model_shape)
    else:
        add('warn', 'error.invalid_model', 'invalid model error shape unexpected', model_shape)

    cap_shape = shape(results.get('invalid_cap', {}))
    if cap_shape['status'] == 400 and cap_shape.get('type') == 'invalid_request_error':
        add('pass', 'error.invalid_cap',
            'max_output_tokens=0 rejected as invalid_request_error', cap_shape)
    elif cap_shape['status'] == 200:
        add('fail', 'error.invalid_cap', 'max_output_tokens=0 was accepted', cap_shape)
    else:
        add('warn', 'error.invalid_cap', 'invalid cap error shape unexpected', cap_shape)

    auth_shape = shape(results.get('unauthorized', {}))
    if auth_shape['status'] in (401, 403) and auth_shape.get('type') in (
            'authentication_error', 'invalid_request_error', 'permission_error'):
        add('pass', 'error.unauthorized',
            'missing credential rejected with an auth error', auth_shape)
    elif auth_shape['status'] == 200:
        add('fail', 'error.unauthorized', 'missing credential was accepted', auth_shape)
    else:
        add('warn', 'error.unauthorized', 'auth error shape unexpected', auth_shape)

    cap_summary = results.get('cap', {}).get('summary', {})
    cap_status = cap_summary.get('status')
    cap_tokens = (cap_summary.get('usage') or {}).get('output_tokens')
    if cap_status == 'incomplete':
        add('pass', 'output.cap', 'max_output_tokens produces status=incomplete')
    elif cap_status == 'completed' and isinstance(cap_tokens, int) and cap_tokens > 8:
        add('fail', 'output.cap',
            'max_output_tokens was ignored (returned more tokens than the cap)',
            {'status': cap_status, 'output_tokens': cap_tokens, 'cap': 8})
    else:
        add('warn', 'output.cap', 'max_output_tokens did not produce status=incomplete',
            {'status': cap_status})

    image_summary = results.get('image', {}).get('summary', {})
    if 'red' in (image_summary.get('text') or '').lower():
        add('pass', 'image.vision', 'image input answered correctly')
    else:
        add('warn', 'image.vision', 'image input not answered as expected',
            {'text': (image_summary.get('text') or '')[:120]})

    chat = results.get('chat', {})
    if chat.get('status') == 200 and isinstance(chat.get('json'), dict):
        add('pass', 'chat.surface', 'Chat Completions surface works')
    else:
        add('warn', 'chat.surface', 'Chat Completions surface failed',
            {'status': chat.get('status')})

    liveness = results.get('catalog_liveness') or {}
    failed = {model: status for model, status in liveness.items() if status != 200}
    if failed:
        add('warn', 'catalog.liveness', 'catalog lists models that fail on chat',
            {'failed': failed, 'checked': liveness})
    elif liveness:
        add('pass', 'catalog.liveness', 'all sampled catalog models answered',
            {'checked': liveness, 'failed': {}})

    repeats = results.get('usage_repeat') or []
    values = []
    for item in repeats:
        if not isinstance(item, dict):
            continue
        usage = (item.get('summary') or {}).get('usage')
        if not isinstance(usage, dict):
            usage = item.get('usage') or {}
        value = usage.get('input_tokens')
        if isinstance(value, int):
            values.append(value)
    if len(values) >= 2 and min(values) > 0:
        ratio = max(values) / min(values)
        if ratio > 1.05:
            add('warn', 'usage.stability', 'same request reports different input_tokens',
                {'values': values, 'ratio': round(ratio, 3)})
        else:
            add('pass', 'usage.stability', 'input_tokens stable across repeats',
                {'values': values})
    elif repeats:
        add('warn', 'usage.stability', 'usage values unavailable',
            {'statuses': [item.get('status') for item in repeats if isinstance(item, dict)]})

    cross_summary = results.get('cross_model', {}).get('summary', {})
    if (cross_summary.get('instructions_sha256')
            and cross_summary.get('instructions_sha256') == summary.get('instructions_sha256')):
        add('info', 'wrapper.shared',
            'same injected instructions across model labels',
            {'target': summary.get('model') or DEFAULT_MODEL, 'other': 'gpt-6-sol'})
    elif cross_summary.get('present'):
        add('pass', 'wrapper.shared', 'model labels use different instructions')

    store_false = (results.get('responses_min', {}).get('summary') or {}).get('store')
    store_true = (results.get('prev_first', {}).get('summary') or {}).get('store')
    if store_false is False and store_true is True:
        add('pass', 'store.echo', 'store flag echoed correctly')
    else:
        add('warn', 'store.echo', 'store flag not echoed as expected',
            {'store_false': store_false, 'store_true': store_true})

    cache = results.get('cache_retention', {})
    if cache.get('status') == 200:
        add('pass', 'cache.retention', 'prompt_cache_retention accepted')
    else:
        add('warn', 'cache.retention', 'prompt_cache_retention not accepted',
            {'status': cache.get('status'), 'error': cache.get('error')})

    verb = results.get('verbosity', {})
    verbosity = ((verb.get('summary') or {}).get('text_config') or {}).get('verbosity')
    if verb.get('status') == 200 and verbosity == 'low':
        add('pass', 'text.verbosity', 'text.verbosity echoed as low')
    elif verb.get('status') == 200:
        add('warn', 'text.verbosity', 'text.verbosity accepted but not echoed',
            {'verbosity': verbosity})
    else:
        add('warn', 'text.verbosity', 'text.verbosity not accepted',
            {'status': verb.get('status'), 'error': verb.get('error')})

    calls = (results.get('tools', {}).get('summary') or {}).get('tool_calls') or []
    if any('B7' in (item.get('arguments') or '') for item in calls):
        add('pass', 'tools.function_call', 'Responses function call produced with expected args')
    else:
        add('warn', 'tools.function_call', 'Responses function call missing or unexpected',
            {'tool_calls': calls, 'status': results.get('tools', {}).get('status')})

    structured_text = (results.get('structured', {}).get('summary') or {}).get('text') or ''
    structured_ok = False
    try:
        value = json.loads(structured_text.strip())
        structured_ok = (isinstance(value, dict) and value.get('city') == '杭州'
                         and value.get('date') == '2026-03-14')
    except ValueError:
        structured_ok = False
    if structured_ok:
        add('pass', 'structured.output', 'JSON schema output matched')
    else:
        add('warn', 'structured.output', 'JSON schema output missing or mismatched',
            {'text': structured_text[:120], 'status': results.get('structured', {}).get('status')})

    add('info', 'identity.undetermined',
        'protocol surface only; model identity is not authenticated')
    fails = sum(item['level'] == 'fail' for item in findings)
    warns = sum(item['level'] == 'warn' for item in findings)
    status = 'inconsistent' if fails else ('partial' if warns else 'consistent')
    return {'status': status, 'findings': findings,
            'counts': {'pass': sum(item['level'] == 'pass' for item in findings),
                       'info': sum(item['level'] == 'info' for item in findings),
                       'warn': warns, 'fail': fails},
            'identity_authenticated': False, 'model_identity': 'undetermined'}


def report(plan, results, verdict):
    meta = results.get('_meta') or {}
    mode = meta.get('mode', plan.get('mode', 'responses'))
    lines = ['# 中转查 · 协议面审计', '',
             f'- 目标：`{plan["base_url"]}`',
             f'- 声明型号：`{plan["model"]}`',
             f'- 模式：`{mode}`',
             f'- 时间：{meta.get("started_asia")}（耗时约 {meta.get("duration_s")} 秒）',
             f'- 请求数：{meta.get("requests")}',
             '', '> 中转查 · 协议面审计：只回答“能不能用、协议面是否像官方”，不认证型号身份。',
             '> 主分只看可用性；协议契约与错误码在检查表和附录中单独标注。', '',
             '## 结论', '',
             f'- 协议面：**{verdict["status"]}**（pass {verdict["counts"]["pass"]} / '
             f'info {verdict["counts"]["info"]} / warn {verdict["counts"]["warn"]} / '
             f'fail {verdict["counts"]["fail"]}）',
             '- 型号身份：**无法判定**（没有独立同版本参照）', '',
             '## 检查表', '', '| 检查 | 结果 | 说明 |', '|---|---|---|']
    for item in verdict['findings']:
        lines.append(f'| `{item["code"]}` | {item["level"]} | {item["message"]} |')

    key = []
    anomaly = []
    if mode == 'chat':
        chat = results.get('chat', {})
        stream = results.get('chat_stream', {})
        tools = results.get('chat_tools', {})
        tool_choices = ((tools.get('json') or {}).get('choices') or [])
        tool_calls = ((tool_choices[0].get('message') or {}).get('tool_calls') or []) if tool_choices else []
        key += [f'- Chat 状态：{chat.get("status")}',
                f'- 流式：status {stream.get("status")}；finish {stream.get("finish_reason")}；'
                f'内容长度 {len(stream.get("text") or "")}',
                f'- 工具调用：{len(tool_calls)} 个',
                f'- 结构化输出：{_chat_content(results.get("chat_structured", {}))[:160]}',
                f'- 视觉：{_chat_content(results.get("chat_vision", {}))[:80]}',
                f'- usage 重复（prompt_tokens）：'
                f'{[((item.get("json") or {}).get("usage") or {}).get("prompt_tokens") for item in results.get("usage_repeat") or []]}',
                f'- 目录抽检：{json.dumps(results.get("catalog_liveness"), ensure_ascii=False)}']
        anomaly += [f'- `chat.tools`：status {tools.get("status")}；calls {len(tool_calls)}',
                    f'- `chat.structured`：status {results.get("chat_structured", {}).get("status")}',
                    f'- `chat.vision`：status {results.get("chat_vision", {}).get("status")}']
    else:
        summary = (results.get('responses_min') or {}).get('summary') or {}
        key += [
            f'- Responses 状态：{results.get("responses_min", {}).get("status")}；'
            f'输出类型：{summary.get("output_types")}；phase：{summary.get("phases")}',
            f'- instructions：{summary.get("instructions_len")} 字符；'
            f'含 Codex：{summary.get("instructions_has_codex")}；'
            f'含 GPT-5：{summary.get("instructions_has_gpt5")}',
            f'- usage：{json.dumps(summary.get("usage"), ensure_ascii=False)}',
            f'- reasoning low/high：'
            f'{(results.get("effort_low", {}).get("summary", {}).get("usage") or {}).get("reasoning_tokens")}'
            f' / '
            f'{(results.get("effort_high", {}).get("summary", {}).get("usage") or {}).get("reasoning_tokens")}',
            f'- 目录抽检：{json.dumps(results.get("catalog_liveness"), ensure_ascii=False)}',
            f'- 同一请求重复（status,input_tokens）：'
            f'{[ (item.get("status"), ((item.get("summary") or {}).get("usage") or {}).get("input_tokens")) for item in results.get("usage_repeat") or [] ]}',
            f'- store：min='
            f'{(results.get("responses_min", {}).get("summary") or {}).get("store")}；'
            f'prev_first='
            f'{(results.get("prev_first", {}).get("summary") or {}).get("store")}']
        anomaly += [
            f'- `previous_response_id`：status '
            f'{results.get("prev_second", {}).get("status")}；text '
            f'{json.dumps((results.get("prev_second", {}).get("summary") or {}).get("text"), ensure_ascii=False)[:120]}；error '
            f'{json.dumps(results.get("prev_second", {}).get("error"), ensure_ascii=False)}',
            f'- `reasoning.effort=none`：status '
            f'{results.get("invalid_effort", {}).get("status")}（官方 gpt-6.1-sol 会 400）',
            f'- `max_output_tokens=8`：status '
            f'{results.get("cap", {}).get("summary", {}).get("status")}；实际 output_tokens '
            f'{(results.get("cap", {}).get("summary", {}).get("usage") or {}).get("output_tokens")}']
    mode_flag = '' if mode == 'auto' else f' --mode {mode}'
    lines += ['', '## 关键观测', '', *key, '', '## 协议面异常证据', '', *anomaly,
              '', '## 适用范围（重要）', '',
              '- 能说明：协议面是否合规、参数契约是否生效、续接/截断/错误码是否像官方、目录是否一致。',
              '- 不能说明：底层权重是不是某个具体型号；同门型号替换（例如 6-sol 冒充 6.1-sol）无法排除。',
              '- 自报、persona、instructions 只能当线索，不能当身份证据。', '',
              '## 复现', '',
              '```sh',
              f'python scripts/gpt_audit.py --base-url {plan["base_url"]} '
              f'--model {plan["model"]} --out NEW-DIRECTORY --enable-remote{mode_flag}',
              '```', '',
              '证据目录含 `PLAN.json`、`RESULTS.json`、`SUMMARY.json`、`REPORT.md`、'
              '`INSTRUCTIONS.txt`（Responses 模式）、`manifest.json`。', '',
              '## 边界', '',
              '- 只覆盖协议/能力/目录/包装，不覆盖“同门型号替换”。',
              '- 结论中的 `identity_authenticated=false` 是固定值，不是本次才有的结论。', '']
    return '\n'.join(lines)


def _read_key_file(path):
    path = Path(path)
    if path.is_symlink():
        raise ContractError('key file symlink refused')
    info = path.stat()
    if stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid():
        raise ContractError('key file must be owner-only 0600')
    values = {}
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep:
            continue
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _env_value(names):
    for name in names:
        value = os.environ.get(name, '').strip()
        if value:
            return value
    return ''


def load_credentials(args):
    if args.api_key_env:
        key = os.environ.get(args.api_key_env, '').strip()
        if not key:
            raise ContractError('API key environment variable is empty')
        base = args.base_url or _env_value(BASE_NAMES)
        if not base:
            raise ContractError('base URL is required (--base-url or BASE_URL in the environment)')
        return base, key, 'env:' + args.api_key_env
    path = Path(args.api_key_file) if args.api_key_file else Path.cwd() / 'config' / 'relay.local.env'
    values = _read_key_file(path)
    key = next((values[name] for name in KEY_NAMES if values.get(name)), None)
    if not key:
        raise ContractError('key file has no supported API key field')
    base = args.base_url or next((values[name] for name in BASE_NAMES if values.get(name)),
                                 _env_value(BASE_NAMES))
    if not base:
        raise ContractError('base URL is required (--base-url or a BASE_URL field)')
    return base, key, 'file:' + str(path.resolve())


def check_base(base, allow_local=False):
    parsed = urlsplit(base)
    local = parsed.hostname in ('127.0.0.1', 'localhost')
    if parsed.scheme != 'https' and not (allow_local and local and parsed.scheme == 'http'):
        raise ContractError('HTTPS base URL required')
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ContractError('base URL must not carry credentials or query')
    if not parsed.hostname:
        raise ContractError('base URL is missing a host')
    return base.rstrip('/')


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--base-url')
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument('--api-key-file', type=Path)
    parser.add_argument('--api-key-env')
    parser.add_argument('--allow-local', action='store_true')
    parser.add_argument('--enable-remote', action='store_true')
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--exclude-model', action='append', default=[])
    parser.add_argument('--catalog-mode', choices=('target', 'sample'), default='target')
    parser.add_argument('--mode', choices=('auto', 'responses', 'chat'), default='auto')
    return parser


def run(args):
    for name, default in (('base_url', None), ('model', DEFAULT_MODEL),
                          ('api_key_file', None), ('api_key_env', None),
                          ('allow_local', False), ('enable_remote', False),
                          ('verify', None), ('out', None), ('exclude_model', []),
                          ('catalog_mode', 'target'), ('mode', 'auto')):
        if not hasattr(args, name):
            setattr(args, name, default)
    if args.verify:
        print(json.dumps(verify_manifest(args.verify), ensure_ascii=False))
        return 0
    if not args.out:
        raise ContractError('--out is required')
    if not args.enable_remote:
        print(json.dumps({'status': 'dry_run', 'requests': 25, 'checks': list(SUITE),
                          'note': 'pass --enable-remote to send'}, ensure_ascii=False))
        return 0
    if args.out.exists() or any(p.is_symlink() for p in (args.out, *args.out.parents)):
        raise ContractError('output exists or symlink refused')
    base, secret, source = load_credentials(args)
    base = check_base(base, args.allow_local)
    args.out.mkdir(parents=True, mode=0o700)
    plan = {'schema': SCHEMA, 'base_url': base, 'model': args.model,
            'mode': getattr(args, 'mode', 'auto'),
            'limits': LIMITS, 'suite': list(SUITE),
            'key_source': source, 'identity_authenticated': False,
            'scope': 'protocol_surface_only_not_model_authentication',
            'source_sha256': digest(Path(__file__).read_bytes())}
    save(args.out / 'PLAN.json', plan, secret)
    with httpx.Client(base_url=base,
                      timeout=httpx.Timeout(LIMITS['request_seconds'], connect=20),
                      trust_env=False, follow_redirects=False) as client:
        results = run_suite(client, secret, args.model,
                            getattr(args, 'exclude_model', []) or [],
                            getattr(args, 'catalog_mode', 'target'),
                            getattr(args, 'mode', 'auto'))
    save(args.out / 'RESULTS.json', {
        key: ({k: v for k, v in value.items() if k != 'completed'}
              if isinstance(value, dict) else value)
        for key, value in results.items()}, secret)
    verdict = assess(results)
    full = (results.get('responses_min') or {}).get('completed') or {}
    if full.get('instructions'):
        (args.out / 'INSTRUCTIONS.txt').write_text(full['instructions'], encoding='utf-8')
    save(args.out / 'SUMMARY.json', {'schema': SCHEMA, 'verdict': verdict, 'results': results})
    (args.out / 'REPORT.md').write_text(report(plan, results, verdict), encoding='utf-8')
    write_manifest(args.out)
    print(json.dumps({'status': verdict['status'], 'counts': verdict['counts'],
                      'evidence': str(args.out.resolve()),
                      'identity_authenticated': False}, ensure_ascii=False))
    return 2 if verdict['status'] == 'inconsistent' else 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except ContractError as error:
        print(json.dumps({'status': 'error', 'error_type': 'ContractError',
                          'message': str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

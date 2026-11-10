import json
from pathlib import Path

from relay_audit import protocol_audit, relay_audit


def _chat_results():
    return {
        '_meta': {'mode': 'chat'},
        'chat': {'status': 200, 'json': {'choices': [{'message': {'content': 'hi'}}],
                                         'usage': {'prompt_tokens': 10}}},
        'chat_stream': {'status': 200, 'finish_reason': 'stop', 'text': 'hi'},
        'chat_tools': {'status': 200, 'json': {'choices': [{'message': {'tool_calls': [
            {'function': {'name': 'lookup_inventory', 'arguments': '{"sku":"B7"}'}}]}}]}},
        'chat_structured': {'status': 200, 'json': {'choices': [{'message': {
            'content': '{"city":"杭州","date":"2026-03-14"}'}}]}},
        'chat_vision': {'status': 200, 'json': {'choices': [{'message': {'content': 'Red'}}]}},
        'usage_repeat': [{'status': 200, 'json': {'usage': {'prompt_tokens': 10}}},
                         {'status': 200, 'json': {'usage': {'prompt_tokens': 10}}}],
        'catalog_liveness': {'gpt-6.1-sol': 200},
    }


def test_responses_available_detection():
    assert protocol_audit.responses_available({'status': 200, 'summary': {'present': True}})
    assert not protocol_audit.responses_available({'status': 404, 'summary': {'present': False}})


def test_chat_assessment_passes():
    verdict = protocol_audit.assess(_chat_results())
    assert verdict['mode'] == 'chat'
    assert verdict['status'] == 'consistent'
    assert verdict['counts']['fail'] == 0


def test_cli_dry_run(tmp_path):
    assert relay_audit.main(['--base-url', 'https://relay.test/v1',
                             '--out', str(tmp_path / 'out')]) == 0


def test_from_audit_builds_branded_html(tmp_path):
    source = tmp_path / 'audit'
    source.mkdir()
    (source / 'PLAN.json').write_text(json.dumps(
        {'base_url': 'https://relay.example/v1', 'model': 'gpt-6.1-sol'}))
    results = _chat_results()
    (source / 'SUMMARY.json').write_text(json.dumps(
        {'verdict': protocol_audit.assess(results), 'results': results}))
    out = tmp_path / 'report'
    code = relay_audit.main(['--from-audit', str(source), '--out', str(out)])
    assert code in (0, 2)
    page = (out / 'REPORT.html').read_text(encoding='utf-8')
    assert '中转查 · 协议面审计' in page
    assert '中转查' in page

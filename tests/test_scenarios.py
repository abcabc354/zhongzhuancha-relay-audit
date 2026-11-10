import json
from pathlib import Path

import pytest

from relay_audit import protocol_scorecard

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'examples' / 'scenarios'
EXPECTED = {
    'responses-good': ('consistent', 'A', 100, 0),
    'chat-only': ('consistent', 'A', 100, 0),
    'wrapper-shell': ('partial', 'A', 100, 0),
    'cap-ignored': ('inconsistent', 'A', 100, 1),
    'prev-unsupported': ('inconsistent', 'A', 100, 1),
    'usage-drift': ('partial', 'A', 92, 0),
}
FORBIDDEN = ('openox', 'micuapi', 'civilian', '8yes', 'beiluoxi', 'openrouter', 'sk-')


def _load(slug):
    return json.loads((FIX / slug / 'SUMMARY.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('slug', sorted(EXPECTED))
def test_scenario_expected_result(slug):
    data = _load(slug)
    verdict = data['verdict']
    card = protocol_scorecard.build({'targets': [{
        'name': slug, 'model': 'gpt-6.1-sol',
        'status': verdict['status'], 'findings': verdict['findings']}]})
    target = card['targets'][0]
    status, grade, coverage, hard = EXPECTED[slug]
    assert verdict['status'] == status
    assert target['overall']['grade'] == grade
    assert target['overall']['coverage'] == coverage
    assert sum(1 for f in verdict['findings'] if f['level'] == 'fail') == hard


def test_fixtures_have_no_real_names_or_keys():
    for path in FIX.rglob('*.json'):
        text = path.read_text(encoding='utf-8').lower()
        for word in FORBIDDEN:
            assert word not in text, f'{path}: {word}'


def test_all_six_scenarios_exist():
    assert sorted(p.name for p in FIX.iterdir() if p.is_dir()) == sorted(EXPECTED)

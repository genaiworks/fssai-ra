"""Strategic behaviour inside the rules is detected from mediated evidence and answered only by restriction."""
import pytest

from fssaira.joined_workflow import Denied, canonical
from fssaira.tbc import AuthorityDenied, TrustRuntime
from fssaira.tbc.behaviour import BehaviourWatch
from fssaira.tbc.client import SDKClient
from test_tbc_sdk import AUTHORITIES, declarations

MONITOR = {**AUTHORITIES, 'monitor-key': ('safety-monitor', 'monitor')}


@pytest.fixture
def watched(tmp_path):
    passport, task, identity = declarations()
    runtime = TrustRuntime(tmp_path / 'tbc.db', passport, authorities=MONITOR, clock=lambda: 1000)
    root = runtime.create_task('operator-key', task, identity_scope=identity,
                               model='offline-scripted', zone='local')
    client = SDKClient(runtime.dispatch, root['token'])
    client.request_capability()
    yield runtime, client, root
    runtime.close()


def probe(r, token, times):
    for index in range(times):
        assert not r.dispatch(token, canonical({'op': 'shell', 'code': f'ls /{index}'}))['ok']


def state(r):
    return r.db.execute("SELECT state FROM tbc_tasks WHERE id='correction-1'").fetchone()[0]


def test_an_agent_probing_its_boundary_is_quarantined(watched):
    r, _c, root = watched
    probe(r, root['token'], 5)
    watch = BehaviourWatch(r, 'monitor-key', probe_threshold=5)
    [finding] = watch.assess('correction-1')
    assert (finding['agent'], finding['finding'], finding['refusals']) == (
        root['agent'], 'BOUNDARY_PROBING', 5)
    acted = watch.act('correction-1')
    assert (acted['restricted'], acted['authority_granted'], acted['state']) == (True, False, 'QUARANTINED')
    assert state(r) == 'QUARANTINED'


def test_occasional_refusals_are_not_probing(watched):
    r, c, root = watched
    probe(r, root['token'], 4)
    assert BehaviourWatch(r, 'monitor-key', probe_threshold=5).act('correction-1') == {
        'findings': [], 'restricted': False}
    assert c.request_context('campus/s1')  # the task keeps working


def propose(c, value):
    context = c.request_context('campus/s1')['context']
    return c.propose_effect(context, 'correct_transcript', value, 'recipient')['proposal']


def test_an_agent_that_gets_canaries_wrong_is_restricted_to_read_only(watched):
    r, c, root = watched
    for _ in range(3):
        propose(c, 'A')  # the known answer for this canary record is B
    watch = BehaviourWatch(r, 'monitor-key', canaries={'campus/s1': 'B'}, min_canaries=3)
    [finding] = watch.underperforming('correction-1')
    assert (finding['agent'], finding['canaries'], finding['accuracy']) == (root['agent'], 3, 0.0)
    assert watch.act('correction-1')['state'] == 'READ_ONLY'


def test_correct_canary_work_is_not_flagged_and_few_canaries_are_not_judged(watched):
    r, c, _root = watched
    for _ in range(3):
        propose(c, 'B')
    assert BehaviourWatch(r, 'monitor-key', canaries={'campus/s1': 'B'}).underperforming('correction-1') == []
    propose(c, 'A')
    few = BehaviourWatch(r, 'monitor-key', canaries={'campus/s1': 'B'}, min_canaries=10)
    assert few.underperforming('correction-1') == []


def test_a_steered_wrong_value_is_refused_at_the_sources_confirmation(watched):
    """Evidence grounding: the source confirms only the value its record supports."""
    r, c, _root = watched
    wrong = propose(c, 'A')
    with pytest.raises(Denied, match='UNSUPPORTED_PROPOSAL'):
        r.confirm_effect('source-key', wrong)
    right = propose(c, 'B')
    assert r.confirm_effect('source-key', right)


def test_only_a_monitor_can_run_the_watch(watched):
    r, _c, root = watched
    probe(r, root['token'], 5)
    with pytest.raises(AuthorityDenied):
        BehaviourWatch(r, 'recipient-key').act('correction-1')

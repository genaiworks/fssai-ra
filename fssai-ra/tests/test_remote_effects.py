"""A remote effect is at most once, and an unknown outcome stays unknown."""
import pytest

from fssaira.remote_effects import (
    CONFIRMED,
    FAILED,
    SENT,
    UNCERTAIN,
    EffectLedger,
    IntegrityViolation,
    LostAcknowledgement,
    ProviderRejected,
    UnresolvedEffect,
    idempotency_key,
)

PAYLOAD = {'student': 's1', 'field': 'grade', 'value': 'B'}


class Provider:
    """A provider that records what it was actually asked to do."""

    def __init__(self, *, behaviour='ok', supports_lookup=True):
        self.behaviour = behaviour
        self.supports_lookup = supports_lookup
        self.submissions = []
        self.lookups = []
        self.effects = {}

    def submit(self, idempotency_key, operation, payload):
        self.submissions.append(idempotency_key)
        if self.behaviour == 'lost':
            # The classic case: the effect landed, the acknowledgement did not.
            self.effects[idempotency_key] = {'status': 'applied', 'ref': 'r-1'}
            raise LostAcknowledgement('no acknowledgement within the deadline')
        if self.behaviour == 'timeout':
            raise TimeoutError('read timed out')
        if self.behaviour == 'rejected':
            raise ProviderRejected('the destination record is locked')
        self.effects[idempotency_key] = {'status': 'applied', 'ref': 'r-1'}
        return {'status': 'applied', 'ref': 'r-1'}

    def lookup(self, idempotency_key):
        self.lookups.append(idempotency_key)
        if not self.supports_lookup:
            return None
        found = self.effects.get(idempotency_key)
        return {'status': 'applied', 'result': found} if found else {'status': 'absent'}


@pytest.fixture
def ledger(tmp_path):
    instance = EffectLedger(tmp_path / 'effects.db')
    yield instance
    instance.close()


def key():
    return idempotency_key(proposal='p-1', approval='a-1',
                           operation='correct_transcript', payload=PAYLOAD)


def submit(ledger, provider, *, effect_key=None):
    return ledger.submit(provider, key=effect_key or key(),
                         operation='correct_transcript', payload=PAYLOAD)


# -- the key ----------------------------------------------------------------


def test_the_key_is_derived_from_the_approved_decision():
    assert key() == key()
    other = idempotency_key(proposal='p-1', approval='a-2',
                            operation='correct_transcript', payload=PAYLOAD)
    assert other != key(), 'a second approval is a second effect, deliberately'


def test_the_key_changes_with_the_payload():
    changed = idempotency_key(proposal='p-1', approval='a-1',
                              operation='correct_transcript',
                              payload={**PAYLOAD, 'value': 'A'})
    assert changed != key()


# -- the happy path and the retry ------------------------------------------


def test_a_confirmed_effect_is_never_submitted_twice(ledger):
    provider = Provider()
    assert submit(ledger, provider).state == CONFIRMED
    assert submit(ledger, provider).state == CONFIRMED
    assert provider.submissions == [key()], 'the provider was called more than once'
    ledger.require_settled()


def test_a_definitively_rejected_effect_is_not_retried(ledger):
    provider = Provider(behaviour='rejected')
    assert submit(ledger, provider).state == FAILED
    assert submit(ledger, provider).state == FAILED
    assert len(provider.submissions) == 1
    ledger.require_settled()   # FAILED is settled: it definitely did not happen


# -- the case this module exists for ---------------------------------------


@pytest.mark.parametrize('behaviour', ['lost', 'timeout'])
def test_an_unacknowledged_call_is_uncertain_not_failed(ledger, behaviour):
    record = submit(ledger, Provider(behaviour=behaviour))
    assert record.state == UNCERTAIN
    assert ledger.unresolved() == (record,)


def test_an_uncertain_effect_is_never_retried_blindly(ledger):
    provider = Provider(behaviour='lost')
    submit(ledger, provider)
    with pytest.raises(UnresolvedEffect):
        submit(ledger, provider)
    assert len(provider.submissions) == 1, 'a retry would have double-applied it'


def test_an_uncertain_effect_blocks_the_work_that_depends_on_it(ledger):
    submit(ledger, Provider(behaviour='lost'))
    with pytest.raises(UnresolvedEffect) as error:
        ledger.require_settled()
    assert UNCERTAIN in str(error.value)


def test_reconciliation_resolves_a_lost_acknowledgement_without_reapplying(ledger):
    provider = Provider(behaviour='lost')
    submit(ledger, provider)
    resolved = ledger.reconcile(provider, key())
    assert resolved.state == CONFIRMED
    assert len(provider.submissions) == 1
    ledger.require_settled()


def test_reconciliation_is_idempotent(ledger):
    provider = Provider(behaviour='lost')
    submit(ledger, provider)
    first = ledger.reconcile(provider, key())
    second = ledger.reconcile(provider, key())
    assert first.state == second.state == CONFIRMED
    assert len(provider.lookups) == 1, 'a settled effect is not re-queried'


def test_a_provider_that_confirms_absence_resolves_to_failed(ledger):
    provider = Provider(behaviour='timeout')
    submit(ledger, provider)
    # Nothing was recorded on the provider side, so the effect did not happen.
    assert ledger.reconcile(provider, key()).state == FAILED


def test_a_provider_without_lookup_leaves_a_permanent_uncertain_remainder(ledger):
    provider = Provider(behaviour='lost', supports_lookup=False)
    submit(ledger, provider)
    record = ledger.reconcile(provider, key())
    assert record.state == UNCERTAIN
    assert 'lookup' in record.detail
    summary = ledger.reconcile_all(provider)
    assert summary['still_uncertain'] and not summary['resolved']
    assert any('exactly-once-observable' in limit for limit in summary['limits'])


def test_an_unavailable_provider_during_reconciliation_changes_nothing(ledger):
    class Unreachable(Provider):
        def lookup(self, idempotency_key):
            raise OSError('provider unreachable')

    provider = Unreachable(behaviour='lost')
    submit(ledger, provider)
    record = ledger.reconcile(provider, key())
    assert record.state == UNCERTAIN
    assert 'unavailable' in record.detail


# -- crash semantics --------------------------------------------------------


def test_a_crash_between_intent_and_acknowledgement_leaves_a_record(tmp_path):
    """The write-ahead property: an effect never leaves without a trace."""
    path = tmp_path / 'effects.db'
    first = EffectLedger(path)

    class Crashing(Provider):
        def submit(self, idempotency_key, operation, payload):
            self.submissions.append(idempotency_key)
            self.effects[idempotency_key] = {'status': 'applied', 'ref': 'r-1'}
            raise KeyboardInterrupt('process killed mid-call')

    provider = Crashing()
    with pytest.raises(KeyboardInterrupt):
        first.submit(provider, key=key(), operation='correct_transcript', payload=PAYLOAD)
    first.close()

    recovered = EffectLedger(path)
    try:
        record = recovered.get(key())
        assert record is not None and record.state == SENT
        # A restart must not resend it; it must reconcile it.
        with pytest.raises(UnresolvedEffect):
            recovered.submit(provider, key=key(), operation='correct_transcript',
                             payload=PAYLOAD)
        assert len(provider.submissions) == 1
        assert recovered.get(key()).state == UNCERTAIN
        assert recovered.reconcile(provider, key()).state == CONFIRMED
    finally:
        recovered.close()


# -- integrity --------------------------------------------------------------


def test_reusing_one_key_for_a_different_payload_is_an_integrity_violation(ledger):
    provider = Provider()
    submit(ledger, provider)
    with pytest.raises(IntegrityViolation):
        ledger.submit(provider, key=key(), operation='correct_transcript',
                      payload={**PAYLOAD, 'value': 'A'})


def test_a_provider_that_changes_its_answer_for_one_key_is_reported(ledger):
    class Inconsistent(Provider):
        def lookup(self, idempotency_key):
            return {'status': 'applied', 'result': {'ref': 'a-different-effect'}}

    provider = Inconsistent()
    submit(ledger, provider)                       # CONFIRMED with result ref r-1
    ledger._write(key(), state=UNCERTAIN)          # force a reconciliation path
    with pytest.raises(IntegrityViolation):
        ledger.reconcile(provider, key())
    assert ledger.get(key()).state == UNCERTAIN


def test_reconcile_all_separates_resolved_remaining_and_violations(ledger):
    provider = Provider(behaviour='lost')
    submit(ledger, provider)
    other = idempotency_key(proposal='p-2', approval='a-2',
                            operation='correct_transcript', payload=PAYLOAD)
    submit(ledger, provider, effect_key=other)
    summary = ledger.reconcile_all(provider)
    assert len(summary['resolved']) == 2
    assert summary['still_uncertain'] == []
    assert summary['integrity_violations'] == []


def test_reconciling_an_unknown_key_is_refused(ledger):
    with pytest.raises(UnresolvedEffect):
        ledger.reconcile(Provider(), 'a' * 64)


@pytest.mark.parametrize('answer', [None, [], {}, {'status': 'pending'}, {'status': 'error'},
                                    {'status': 'applied'}, {'status': 'applied', 'result': None}])
def test_nonfinal_or_malformed_lookup_never_unblocks_work(ledger, answer):
    class Ambiguous(Provider):
        def lookup(self, idempotency_key):
            return answer
    provider = Ambiguous(behaviour='lost')
    submit(ledger, provider)
    assert ledger.reconcile(provider, key()).state == UNCERTAIN
    with pytest.raises(UnresolvedEffect):
        ledger.require_settled()
    assert len(provider.submissions) == 1


@pytest.mark.parametrize('answer', [None, [], {}, {'status': 'pending'}, {'status': 'accepted'}])
def test_nonfinal_acknowledgement_is_uncertain(ledger, answer):
    class Ambiguous(Provider):
        def submit(self, idempotency_key, operation, payload):
            self.submissions.append(idempotency_key)
            return answer
    provider = Ambiguous()
    assert submit(ledger, provider).state == UNCERTAIN
    with pytest.raises(UnresolvedEffect):
        submit(ledger, provider)
    assert len(provider.submissions) == 1


def test_idempotency_key_cannot_be_rebound_to_another_operation(ledger):
    provider = Provider()
    submit(ledger, provider)
    with pytest.raises(IntegrityViolation):
        ledger.submit(provider, key=key(), operation='delete_transcript', payload=PAYLOAD)
    assert len(provider.submissions) == 1

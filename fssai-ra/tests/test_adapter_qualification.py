"""Qualify real stores and sinks, and prove the qualifier catches broken ones."""
from fssaira.adapter_qualification import (
    QualificationCode,
    SqlAuthorityStore,
    SqlSink,
    audit_linearization,
    concurrent_revocation_check,
    qualify,
)
from fssaira.revocation_chaos import ChaosConfig


class EpochBlindStore(SqlAuthorityStore):
    """Broken on purpose: trusts the adapter's epoch instead of checking its own."""

    def commit(self, effect, task, epoch, now):
        return super().commit(effect, task, self.epoch(task), now)


class KeylessSink(SqlSink):
    """Broken on purpose: no idempotency key."""

    sent = 0

    def deliver(self, effect):
        self.sent += 1
        self.db.execute("INSERT INTO deliveries VALUES(?, 0)", (f"{effect}#{self.sent}",))
        return True


def factories(tmp_path, store_cls=SqlAuthorityStore, sink_cls=SqlSink):
    return (lambda seed, tasks: store_cls(tmp_path / f"store-{seed}.db", tasks),
            lambda seed: sink_cls(tmp_path / f"sink-{seed}.db"))


def test_reference_sql_store_and_sink_qualify(tmp_path):
    result = qualify(*factories(tmp_path), seeds=15)
    assert result['code'] == QualificationCode.QUALIFIED
    assert result['applied'] > 0 and result['refused_stale'] > 0
    assert result['stale_effects'] == result['duplicate_applications'] == result['unreconciled'] == 0


def test_a_store_that_forgets_the_epoch_is_not_qualified(tmp_path):
    result = qualify(*factories(tmp_path, store_cls=EpochBlindStore), seeds=15)
    assert result['code'] == QualificationCode.NOT_QUALIFIED and result['stale_effects'] > 0


def test_a_sink_without_idempotency_keys_is_not_qualified(tmp_path):
    result = qualify(*factories(tmp_path, sink_cls=KeylessSink), seeds=15)
    assert not result['qualified'] and result['duplicate_applications'] > 0


def test_harsh_networks_do_not_break_the_reference_pair(tmp_path):
    harsh = ChaosConfig(duplicate_rate=0.5, loss_rate=0.3, partitions_per_adapter=5, max_skew=30)
    assert qualify(*factories(tmp_path), seeds=8, config=harsh)['qualified']


def test_real_threads_racing_revocation_linearize(tmp_path):
    store = SqlAuthorityStore(tmp_path / 'race.db', tasks=3)
    try:
        result = concurrent_revocation_check(store, tasks=3, workers=6, commits_per_worker=40)
    finally:
        store.close()
    assert result['code'] == QualificationCode.LINEARIZABLE
    assert result['commits'] > 0 and result['revocations'] == 12


def test_the_log_auditor_catches_a_commit_at_a_superseded_epoch():
    log = [('commit', 0, 0, 'a'), ('revoke', 0, 1, None), ('commit', 0, 1, 'b'),
           ('commit', 0, 0, 'late')]
    [violation] = audit_linearization(log)
    assert violation['effect'] == 'late' and violation['current'] == 1
    assert audit_linearization(log[:3]) == []

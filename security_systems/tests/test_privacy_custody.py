"""Envelope encryption, per-subject keys, and cryptographic erasure, on every world."""
import pytest

from trustkernel.kernel.key_custody import CustodyDenied
from trustkernel.world import ScenarioWorld, available_worlds


def test_digits_inside_a_token_are_not_mistaken_for_a_phone_number():
    """Regression: a token whose hex code is all digits was detected as a phone number.

    Tokens carry a random 10-character hex code. Roughly one run in forty produced a
    digit run long enough to match the phone detector, so an output that held only
    tokens was refused as containing undeclared contact details.
    """
    from trustkernel.kernel.privacy_vault import TokenVault

    for token in ("[[OWNER_NAME_1234567890]]", "[[EMAIL_0000000000]]", "[[ID_9876543210]]"):
        assert TokenVault.detect_contact_details(f"{token} needs support; call {token}") == []
    # Digits on either side of a masked token must not join into a false match across it.
    assert TokenVault.detect_contact_details("room 12 [[NAME_1234567890]] 34 ok") == []
    found = TokenVault.detect_contact_details("[[NAME_1234567890]] call +1 415 555 0100")
    assert found == [("PHONE", "+1 415 555 0100")]


@pytest.mark.parametrize("world", available_worlds())
def test_restoring_a_key_backup_without_the_journal_is_refused(world):
    world = ScenarioWorld(world)
    backup = world.custody.backup(world._erase_key)
    world.erasure.erase(world.spec.fixture("subject"), erased_by=world.spec.fixture("data_officer"), reason="synthetic")
    with pytest.raises(CustodyDenied):
        world.custody.restore(world._erase_key, backup, None)
    with pytest.raises(CustodyDenied):
        world.custody.restore(world._erase_key, backup, [])

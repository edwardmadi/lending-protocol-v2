from textwrap import dedent

import boa
import pytest
from eth_utils import decode_hex

from ...conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    CollateralStatus,
    Loan,
    Offer,
    Signature,
    SignedOffer,
    compute_loan_hash,
    compute_signed_offer_id,
    deploy_reverts,
    get_last_event,
    sign_offer,
)


@pytest.fixture
def broker():
    return boa.env.generate_address()


@pytest.fixture
def protocol_fee(p2p_nfts_eth):
    fee = p2p_nfts_eth.max_protocol_fee()
    p2p_nfts_eth.set_protocol_fee(fee, sender=p2p_nfts_eth.owner())
    return fee


@pytest.fixture
def offer_bayc(now, lender, lender_key, bayc, broker, p2p_nfts_eth):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=10,
        broker_fee_bps=2000,
        broker_address=broker,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=1
    )
    return sign_offer(offer, lender_key, p2p_nfts_eth.address)


@pytest.fixture
def offer_bayc2(now, lender2, lender2_key, bayc, broker, p2p_nfts_eth):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=150,
        origination_fee_amount=10,
        broker_fee_bps=200,
        broker_address=broker,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender2,
        pro_rata=False,
        size=1
    )
    return sign_offer(offer, lender2_key, p2p_nfts_eth.address)


@pytest.fixture
def ongoing_loan_bayc(p2p_nfts_eth, offer_bayc, weth, borrower, lender, bayc, now, protocol_fee):

    offer = offer_bayc.offer
    token_id = offer.collateral_min_token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal - origination_fee, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    loan_id = p2p_nfts_eth.create_loan(offer_bayc, token_id, borrower, sender=borrower)

    loan = Loan(
        id=loan_id,
        amount=offer.principal,
        interest=offer.interest,
        payment_token=offer.payment_token,
        maturity=now + offer.duration,
        start_time=now,
        borrower=borrower,
        lender=lender,
        collateral_contract=bayc.address,
        collateral_token_id=token_id,
        origination_fee_amount=offer.origination_fee_amount,
        broker_fee_bps=offer.broker_fee_bps,
        broker_address=offer.broker_address,
        protocol_fee_bps=p2p_nfts_eth.protocol_fee(),
        pro_rata=offer.pro_rata
    )
    assert compute_loan_hash(loan) == p2p_nfts_eth.loans(loan_id)
    return loan


@pytest.fixture
def ongoing_loan_prorata(p2p_nfts_eth, offer_bayc, weth, borrower, lender, bayc, now, lender_key):

    offer = Offer(**offer_bayc.offer._asdict() | {"pro_rata": True})
    token_id = offer.collateral_min_token_id
    principal = offer.principal
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal - origination_fee, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)
    loan_id = p2p_nfts_eth.create_loan(signed_offer, token_id, borrower, sender=borrower)

    loan = Loan(
        id=loan_id,
        amount=offer.principal,
        interest=offer.interest,
        payment_token=offer.payment_token,
        maturity=now + offer.duration,
        start_time=now,
        borrower=borrower,
        lender=lender,
        collateral_contract=bayc.address,
        collateral_token_id=token_id,
        origination_fee_amount=offer.origination_fee_amount,
        broker_fee_bps=offer.broker_fee_bps,
        broker_address=offer.broker_address,
        protocol_fee_bps=p2p_nfts_eth.protocol_fee(),
        pro_rata=offer.pro_rata
    )
    assert compute_loan_hash(loan) == p2p_nfts_eth.loans(loan_id)
    return loan


def test_replace_loan_reverts_if_loan_invalid(p2p_nfts_eth, ongoing_loan_bayc, offer_bayc2):
    invalid_loans = [
        Loan(**ongoing_loan_bayc._asdict() | {"id": ZERO_BYTES32}),
        Loan(**ongoing_loan_bayc._asdict() | {"amount": ongoing_loan_bayc.amount + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"interest": ongoing_loan_bayc.interest + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"payment_token": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"maturity": ongoing_loan_bayc.maturity - 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"start_time": ongoing_loan_bayc.start_time - 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"borrower": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"lender": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"collateral_contract": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"collateral_token_id": ongoing_loan_bayc.collateral_token_id + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"origination_fee_amount": ongoing_loan_bayc.origination_fee_amount + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"broker_fee_bps": ongoing_loan_bayc.broker_fee_bps + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"broker_address": p2p_nfts_eth.address}),
        Loan(**ongoing_loan_bayc._asdict() | {"protocol_fee_bps": ongoing_loan_bayc.protocol_fee_bps + 1}),
        Loan(**ongoing_loan_bayc._asdict() | {"pro_rata": not ongoing_loan_bayc.pro_rata})
    ]

    for loan in invalid_loans:
        print(f"{loan=}")
        with boa.reverts("invalid loan"):
            p2p_nfts_eth.replace_loan(loan, offer_bayc2, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_loan_defaulted(p2p_nfts_eth, ongoing_loan_bayc, now, offer_bayc2):
    time_to_default = ongoing_loan_bayc.maturity - now
    boa.env.time_travel(seconds=time_to_default + 1)

    with boa.reverts("loan defaulted"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_loan_already_settled(p2p_nfts_eth, ongoing_loan_bayc, offer_bayc2):
    loan = ongoing_loan_bayc
    interest = loan.interest
    amount_to_settle = loan.amount + interest

    p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle)

    with boa.reverts("invalid loan"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_offer_not_signed_by_lender(p2p_nfts_eth, borrower_key, ongoing_loan_bayc, offer_bayc2):
    signed_offer = sign_offer(offer_bayc2.offer, borrower_key, p2p_nfts_eth.address)

    with boa.reverts("offer not signed by lender"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, signed_offer, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_offer_has_invalid_signature(p2p_nfts_eth, ongoing_loan_bayc, now, offer_bayc2, lender_key):
    offer = offer_bayc2.offer
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    invalid_offers = [
        Offer(**offer._asdict() | {"principal": offer.principal + 1}),
        Offer(**offer._asdict() | {"interest": offer.interest + 1}),
        Offer(**offer._asdict() | {"payment_token": boa.env.generate_address("random")}),
        Offer(**offer._asdict() | {"duration": offer.duration + 1}),
        Offer(**offer._asdict() | {"origination_fee_amount": offer.origination_fee_amount + 1}),
        Offer(**offer._asdict() | {"broker_fee_bps": offer.broker_fee_bps + 1}),
        Offer(**offer._asdict() | {"broker_address": boa.env.generate_address("random")}),
        Offer(**offer._asdict() | {"collateral_contract": boa.env.generate_address("random")}),
        Offer(**offer._asdict() | {"collateral_min_token_id": offer.collateral_min_token_id + 1}),
        Offer(**offer._asdict() | {"collateral_max_token_id": offer.collateral_max_token_id + 1}),
        Offer(**offer._asdict() | {"expiration": offer.expiration + 1}),
        Offer(**offer._asdict() | {"lender": boa.env.generate_address("random")}),
        Offer(**offer._asdict() | {"pro_rata": not offer.pro_rata}),
        Offer(**offer._asdict() | {"size": offer.size + 1})
    ]

    for invalid_offer in invalid_offers:
        print(f"{invalid_offer=}")
        with boa.reverts("offer not signed by lender"):
            signed_offer = SignedOffer(invalid_offer, signed_offer.signature)
            p2p_nfts_eth.replace_loan(ongoing_loan_bayc, signed_offer, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_offer_expired(p2p_nfts_eth, now, lender, lender_key, bayc, ongoing_loan_bayc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now,
        lender=lender,
        pro_rata=False
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("offer expired"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, signed_offer, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_payment_token_invalid(p2p_nfts_eth, ongoing_loan_bayc, now, lender, lender_key, bayc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=boa.env.generate_address("random"),
        duration=100,
        origination_fee_amount=0,
        broker_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("invalid payment token"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, signed_offer, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_collateral_not_whitelisted(p2p_nfts_eth, p2p_control, ongoing_loan_bayc, offer_bayc2, bayc):

    p2p_control.change_whitelisted_collections([(bayc.address, False)], sender=p2p_control.owner())

    with boa.reverts("collateral not whitelisted"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_token_id_below_offer_range(p2p_nfts_eth, now, ongoing_loan_bayc, lender, lender_key, bayc):
    token_id = ongoing_loan_bayc.collateral_token_id
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id + 1,
        collateral_max_token_id=token_id + 1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("tokenid below offer range"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, signed_offer, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_token_id_above_offer_range(p2p_nfts_eth, now, ongoing_loan_bayc, lender, lender_key, bayc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id - 1,
        collateral_max_token_id=token_id - 1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("tokenid above offer range"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, signed_offer, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_offer_is_revoked(p2p_nfts_eth, borrower, now, ongoing_loan_bayc, offer_bayc2, bayc):

    p2p_nfts_eth.revoke_offer(offer_bayc2, sender=offer_bayc2.offer.lender)

    with boa.reverts("offer revoked"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_offer_exceeds_count(p2p_nfts_eth, ongoing_loan_bayc, now, lender, lender_key, bayc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id - 1,
        collateral_max_token_id=token_id + 1,
        expiration=now + 100,
        lender=lender,
        pro_rata=False,
        size=0
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("offer fully utilized"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, signed_offer, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_origination_fee_exceeds_principal(p2p_nfts_eth, ongoing_loan_bayc, now, lender, lender_key, bayc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=1001,
        broker_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("origination fee gt principal"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, signed_offer, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_broker_fee_without_address(p2p_nfts_eth, ongoing_loan_bayc, now, lender, lender_key, bayc):
    token_id = 1
    offer = Offer(
        principal=1000,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_fee_bps=100,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    with boa.reverts("broker fee without address"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, signed_offer, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_collateral_contract_mismatch(p2p_nfts_eth, p2p_control, ongoing_loan_bayc, now, lender, lender_key, bayc, weth):
    token_id = 1
    principal = 1000
    dummy_contract = boa.env.generate_address("random")
    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=dummy_contract,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    p2p_control.change_whitelisted_collections([(dummy_contract, True)], sender=p2p_control.owner())

    with boa.reverts("collateral contract mismatch"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, signed_offer, sender=ongoing_loan_bayc.borrower)


def test_replace_loan_reverts_if_lender_funds_not_approved(p2p_nfts_eth, borrower, now, lender, lender_key, bayc, weth):
    token_id = 1
    principal = 1000
    offer = Offer(
        principal=principal,
        interest=100,
        payment_token=ZERO_ADDRESS,
        duration=100,
        origination_fee_amount=0,
        broker_fee_bps=0,
        broker_address=ZERO_ADDRESS,
        collateral_contract=bayc.address,
        collateral_min_token_id=token_id,
        collateral_max_token_id=token_id,
        expiration=now + 100,
        lender=lender,
        pro_rata=False
    )
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal, sender=lender)

    with boa.reverts():
        p2p_nfts_eth.create_loan(signed_offer, token_id, ZERO_ADDRESS, sender=borrower)


def test_replace_loan_reverts_if_funds_not_sent(p2p_nfts_eth, ongoing_loan_bayc, weth, offer_bayc2):
    offer = offer_bayc2.offer
    new_lender = offer.lender
    borrower = ongoing_loan_bayc.borrower
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest - (offer.principal - offer.origination_fee_amount)
    weth.deposit(value=principal, sender=new_lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=new_lender)

    with boa.reverts("invalid sent value"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=borrower, value=amount_to_settle - 1)


def test_replace_loan_reverts_if_collateral_locked(p2p_nfts_eth, p2p_control, ongoing_loan_bayc, now, offer_bayc2, weth):
    token_id = ongoing_loan_bayc.collateral_token_id
    collateral_contract = ongoing_loan_bayc.collateral_contract
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    lender = offer.lender
    broker = boa.env.generate_address("random")
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    # simulate previous broker lock
    p2p_control.add_broker_lock(collateral_contract, token_id, broker, now + 100, sender=p2p_nfts_eth.address)

    with boa.reverts("collateral locked"):
        p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=borrower, value=amount_to_settle)


def test_replace_loan(p2p_nfts_eth, ongoing_loan_bayc, offer_bayc2, now, bayc, weth):
    offer = offer_bayc2.offer
    lender = offer.lender
    borrower = ongoing_loan_bayc.borrower
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    loan_id = p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=borrower, value=amount_to_settle)

    loan = Loan(
        id=loan_id,
        amount=offer.principal,
        interest=offer.interest,
        payment_token=offer.payment_token,
        maturity=now + offer.duration,
        start_time=now,
        borrower=ongoing_loan_bayc.borrower,
        lender=lender,
        collateral_contract=bayc.address,
        collateral_token_id=ongoing_loan_bayc.collateral_token_id,
        origination_fee_amount=offer.origination_fee_amount,
        broker_fee_bps=offer.broker_fee_bps,
        broker_address=offer.broker_address,
        protocol_fee_bps=p2p_nfts_eth.protocol_fee(),
        pro_rata=offer.pro_rata
    )
    assert compute_loan_hash(loan) == p2p_nfts_eth.loans(loan_id)


def test_replace_loan_logs_event(p2p_nfts_eth, ongoing_loan_bayc, offer_bayc2, now, bayc, weth):
    token_id = 1
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    lender = offer.lender
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    protocol_fee_amount = ongoing_loan_bayc.interest * ongoing_loan_bayc.protocol_fee_bps // 10000
    broker_fee_amount = ongoing_loan_bayc.interest * ongoing_loan_bayc.broker_fee_bps // 10000
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    loan_id = p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=borrower, value=amount_to_settle)

    event = get_last_event(p2p_nfts_eth, "LoanReplaced")
    assert event.id == loan_id
    assert event.amount == offer.principal
    assert event.interest == offer.interest
    assert event.payment_token == offer.payment_token
    assert event.maturity == now + offer.duration
    assert event.start_time == now
    assert event.borrower == ongoing_loan_bayc.borrower
    assert event.lender == lender
    assert event.collateral_contract == bayc.address
    assert event.collateral_token_id == token_id
    assert event.origination_fee_amount == offer.origination_fee_amount
    assert event.broker_fee == offer.broker_fee_bps
    assert event.broker_address == offer.broker_address
    assert event.protocol_fee == p2p_nfts_eth.protocol_fee()
    assert event.pro_rata == offer.pro_rata
    assert event.original_loan_id == ongoing_loan_bayc.id
    assert event.paid_principal == ongoing_loan_bayc.amount
    assert event.paid_interest == ongoing_loan_bayc.interest
    assert event.paid_protocol_fees == protocol_fee_amount
    assert event.paid_broker_fees == broker_fee_amount


def test_replace_loan_succeeds_if_broker_matches_lock(p2p_nfts_eth, p2p_control, ongoing_loan_bayc, now, offer_bayc2, weth):
    token_id = ongoing_loan_bayc.collateral_token_id
    collateral_contract = ongoing_loan_bayc.collateral_contract
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    lender = offer.lender
    broker = offer.broker_address
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    # simulate previous broker lock
    p2p_control.add_broker_lock(collateral_contract, token_id, broker, now + 100, sender=p2p_nfts_eth.address)

    p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=borrower, value=amount_to_settle)

    collateral_status = CollateralStatus.from_tuple(p2p_control.get_collateral_status(collateral_contract, token_id))
    assert collateral_status.broker_lock.expiration > now
    assert collateral_status.whitelisted


def test_replace_loan_keeps_delegation(p2p_nfts_eth, ongoing_loan_bayc, offer_bayc2, bayc, delegation_registry, weth):
    token_id = 1
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    lender = offer.lender
    delegate = ongoing_loan_bayc.borrower
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    assert delegation_registry.checkDelegateForERC721(delegate, p2p_nfts_eth.address, bayc.address, token_id, b"")

    p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=borrower, value=amount_to_settle)

    assert delegation_registry.checkDelegateForERC721(delegate, p2p_nfts_eth.address, bayc.address, token_id, b"")


def test_replace_loan_keeps_collateral_to_escrow(p2p_nfts_eth, ongoing_loan_bayc, offer_bayc2, bayc, weth):
    token_id = 1
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    lender = offer.lender
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    assert bayc.ownerOf(token_id) == p2p_nfts_eth.address

    p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=borrower, value=amount_to_settle)

    assert bayc.ownerOf(token_id) == p2p_nfts_eth.address


def test_replace_loan_transfers_principal_to_borrower(p2p_nfts_eth, ongoing_loan_bayc, offer_bayc2, weth):
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    new_lender = offer.lender
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    weth.deposit(value=principal, sender=new_lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=new_lender)

    origination_fee = offer.origination_fee_amount
    initial_borrower_balance = boa.env.get_balance(borrower)

    p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=borrower, value=amount_to_settle)

    assert boa.env.get_balance(borrower) == initial_borrower_balance - amount_to_settle + principal - origination_fee


def test_replace_loan_transfers_origination_fee_to_lender(p2p_nfts_eth, ongoing_loan_bayc, offer_bayc2, weth):
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    new_lender = offer.lender
    principal = offer.principal
    origination_fee = offer.origination_fee_amount
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest

    initial_lender_balance = boa.env.get_balance(new_lender)
    weth.deposit(value=principal - origination_fee, sender=new_lender)
    weth.approve(p2p_nfts_eth.address, principal - origination_fee, sender=new_lender)

    p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=borrower, value=amount_to_settle)

    assert boa.env.get_balance(new_lender) == initial_lender_balance - principal + origination_fee


def test_replace_loan_updates_offer_usage_count(p2p_nfts_eth, ongoing_loan_bayc, offer_bayc2, weth):
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    lender = offer.lender
    principal = offer.principal
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    weth.deposit(value=principal, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=lender)

    principal = offer.principal

    assert p2p_nfts_eth.offer_count(compute_signed_offer_id(offer_bayc2)) == 0

    p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=borrower, value=amount_to_settle)

    assert p2p_nfts_eth.offer_count(compute_signed_offer_id(offer_bayc2)) == 1


def test_replace_loan_pays_lender(p2p_nfts_eth, ongoing_loan_bayc, offer_bayc2, weth):
    loan = ongoing_loan_bayc
    offer = offer_bayc2.offer
    borrower = ongoing_loan_bayc.borrower
    lender = ongoing_loan_bayc.lender
    new_lender = offer.lender
    principal = offer.principal
    interest = loan.interest
    protocol_fee_amount = interest * loan.protocol_fee_bps // 10000
    broker_fee_amount = interest * loan.broker_fee_bps // 10000
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    amount_to_receive = loan.amount + interest - protocol_fee_amount - broker_fee_amount

    initial_lender_balance = boa.env.get_balance(lender)

    weth.deposit(value=principal, sender=new_lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=new_lender)

    p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=borrower, value=amount_to_settle)

    assert boa.env.get_balance(loan.lender) == initial_lender_balance + amount_to_receive


def test_replace_loan_pays_borrower_if_amount_to_settle_negative(p2p_nfts_eth, ongoing_loan_bayc, offer_bayc, weth, lender, lender_key):
    loan = ongoing_loan_bayc
    offer = Offer(**offer_bayc.offer._asdict() | {"principal": loan.amount * 2})
    borrower = ongoing_loan_bayc.borrower
    lender = ongoing_loan_bayc.lender
    new_lender = offer.lender
    principal = offer.principal
    interest = loan.interest
    protocol_fee_amount = interest * loan.protocol_fee_bps // 10000
    broker_fee_amount = interest * loan.broker_fee_bps // 10000
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest - (offer.principal - offer.origination_fee_amount)
    amount_to_receive = loan.amount + interest - protocol_fee_amount - broker_fee_amount

    initial_lender_balance = boa.env.get_balance(lender)
    initial_borrower_balance = boa.env.get_balance(borrower)

    weth.deposit(value=principal, sender=new_lender)
    weth.approve(p2p_nfts_eth.address, principal, sender=new_lender)

    p2p_nfts_eth.replace_loan(ongoing_loan_bayc, sign_offer(offer, lender_key, p2p_nfts_eth.address), sender=borrower)

    assert amount_to_settle < 0
    assert boa.env.get_balance(loan.borrower) == initial_borrower_balance - amount_to_settle


def test_replace_loan_pays_broker_fees(p2p_nfts_eth, ongoing_loan_bayc, offer_bayc2, weth):
    loan = ongoing_loan_bayc
    borrower = ongoing_loan_bayc.borrower
    new_lender = offer_bayc2.offer.lender
    new_principal = offer_bayc2.offer.principal
    interest = loan.interest
    broker_fee_amount = interest * loan.broker_fee_bps // 10000
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    initial_broker_balance = boa.env.get_balance(loan.broker_address)

    weth.deposit(value=new_principal, sender=new_lender)
    weth.approve(p2p_nfts_eth.address, new_principal, sender=new_lender)

    p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=borrower, value=amount_to_settle)

    assert boa.env.get_balance(loan.broker_address) == initial_broker_balance + broker_fee_amount


def test_replace_loan_pays_protocol_fees(p2p_nfts_eth, ongoing_loan_bayc, weth, offer_bayc2):
    loan = ongoing_loan_bayc
    borrower = ongoing_loan_bayc.borrower
    new_lender = offer_bayc2.offer.lender
    new_principal = offer_bayc2.offer.principal
    interest = loan.interest
    protocol_fee_amount = interest * loan.protocol_fee_bps // 10000
    amount_to_settle = ongoing_loan_bayc.amount + ongoing_loan_bayc.interest
    initial_protocol_wallet_balance = boa.env.get_balance(p2p_nfts_eth.protocol_wallet())

    weth.deposit(value=new_principal, sender=new_lender)
    weth.approve(p2p_nfts_eth.address, new_principal, sender=new_lender)

    p2p_nfts_eth.replace_loan(ongoing_loan_bayc, offer_bayc2, sender=borrower, value=amount_to_settle)

    assert boa.env.get_balance(p2p_nfts_eth.protocol_wallet()) == initial_protocol_wallet_balance + protocol_fee_amount


def test_replace_loan_prorata_reverts_if_funds_not_sent(p2p_nfts_eth, ongoing_loan_prorata, weth):
    loan = ongoing_loan_prorata
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    amount_to_settle = amount + interest

    boa.env.time_travel(seconds=actual_duration)
    with boa.reverts("invalid sent value"):
        p2p_nfts_eth.settle_loan(loan, sender=loan.borrower, value=amount_to_settle - 1)


def test_replace_loan_prorata_logs_event(p2p_nfts_eth, ongoing_loan_prorata, weth, now, offer_bayc2):
    loan = ongoing_loan_prorata
    offer = offer_bayc2.offer
    borrower = loan.borrower
    new_lender = offer.lender
    new_principal = offer.principal
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.protocol_fee_bps // 10000
    broker_fee_amount = interest * loan.broker_fee_bps // 10000
    amount_to_settle = amount + interest

    weth.deposit(value=new_principal, sender=new_lender)
    weth.approve(p2p_nfts_eth.address, new_principal, sender=new_lender)

    print(f"{amount_to_settle=}")
    boa.env.time_travel(seconds=actual_duration)
    loan_id = p2p_nfts_eth.replace_loan(loan, offer_bayc2, sender=borrower, value=amount_to_settle)

    event = get_last_event(p2p_nfts_eth, "LoanReplaced")
    assert event.id == loan_id
    assert event.amount == offer.principal
    assert event.interest == offer.interest
    assert event.payment_token == offer.payment_token
    assert event.maturity == now + actual_duration + offer.duration
    assert event.start_time == now + actual_duration
    assert event.borrower == loan.borrower
    assert event.lender == new_lender
    assert event.collateral_contract == loan.collateral_contract
    assert event.collateral_token_id == loan.collateral_token_id
    assert event.origination_fee_amount == offer.origination_fee_amount
    assert event.broker_fee == offer.broker_fee_bps
    assert event.broker_address == offer.broker_address
    assert event.protocol_fee == p2p_nfts_eth.protocol_fee()
    assert event.pro_rata == offer.pro_rata
    assert event.original_loan_id == loan.id
    assert event.paid_principal == loan.amount
    assert event.paid_interest == interest
    assert event.paid_protocol_fees == protocol_fee_amount
    assert event.paid_broker_fees == broker_fee_amount


def test_replace_loan_prorata_pays_lender(p2p_nfts_eth, ongoing_loan_prorata, weth, offer_bayc2):
    loan = ongoing_loan_prorata
    offer = offer_bayc2.offer
    borrower = loan.borrower
    new_lender = offer.lender
    new_principal = offer.principal
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.protocol_fee_bps // 10000
    broker_fee_amount = interest * loan.broker_fee_bps // 10000
    amount_to_settle = amount + interest
    amount_to_receive = amount + interest - protocol_fee_amount - broker_fee_amount
    initial_lender_balance = boa.env.get_balance(loan.lender)

    weth.deposit(value=new_principal, sender=new_lender)
    weth.approve(p2p_nfts_eth.address, new_principal, sender=new_lender)

    print(f"{amount_to_settle=}")
    boa.env.time_travel(seconds=actual_duration)
    p2p_nfts_eth.replace_loan(loan, offer_bayc2, sender=borrower, value=amount_to_settle)

    assert boa.env.get_balance(loan.lender) == initial_lender_balance + amount_to_receive


def test_replace_loan_prorata_pays_broker_fees(p2p_nfts_eth, ongoing_loan_prorata, weth, offer_bayc2):
    loan = ongoing_loan_prorata
    offer = offer_bayc2.offer
    borrower = loan.borrower
    new_lender = offer.lender
    new_principal = offer.principal
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    broker_fee_amount = interest * loan.broker_fee_bps // 10000
    amount_to_settle = amount + interest
    initial_broker_balance = boa.env.get_balance(loan.broker_address)

    weth.deposit(value=new_principal, sender=new_lender)
    weth.approve(p2p_nfts_eth.address, new_principal, sender=new_lender)

    print(f"{amount_to_settle=}")
    boa.env.time_travel(seconds=actual_duration)
    p2p_nfts_eth.replace_loan(loan, offer_bayc2, sender=borrower, value=amount_to_settle)

    assert boa.env.get_balance(loan.broker_address) == initial_broker_balance + broker_fee_amount


def test_replace_loan_prorata_pays_protocol_fees(p2p_nfts_eth, ongoing_loan_prorata, weth, offer_bayc2):
    loan = ongoing_loan_prorata
    offer = offer_bayc2.offer
    borrower = loan.borrower
    new_lender = offer.lender
    new_principal = offer.principal
    loan_duration = loan.maturity - loan.start_time
    actual_duration = loan_duration * 2 // 3
    amount = loan.amount
    interest = loan.interest * actual_duration // loan_duration
    protocol_fee_amount = interest * loan.protocol_fee_bps // 10000
    amount_to_settle = amount + interest
    initial_protocol_wallet_balance = boa.env.get_balance(p2p_nfts_eth.protocol_wallet())

    weth.deposit(value=new_principal, sender=new_lender)
    weth.approve(p2p_nfts_eth.address, new_principal, sender=new_lender)

    print(f"{amount_to_settle=}")
    boa.env.time_travel(seconds=actual_duration)
    p2p_nfts_eth.replace_loan(loan, offer_bayc2, sender=borrower, value=amount_to_settle)

    assert boa.env.get_balance(p2p_nfts_eth.protocol_wallet()) == initial_protocol_wallet_balance + protocol_fee_amount


@pytest.mark.parametrize("pro_rata", [True, False])
@pytest.mark.parametrize("same_lender", [True, False])
@pytest.mark.parametrize("principal_loan1", [100000, 200000])
@pytest.mark.parametrize("principal_loan2", [100000, 200000])
def test_replace_loan_settles_amounts(  # noqa: PLR0914
    p2p_nfts_eth,
    offer_bayc,
    bayc,
    weth,
    borrower,
    lender,
    lender_key,
    lender2,
    lender2_key,
    now,
    pro_rata,
    same_lender,
    principal_loan1,
    principal_loan2,
    debug_precompile
):

    p2p_nfts_eth.set_protocol_fee(300)
    offer = Offer(**offer_bayc.offer._asdict() | {
        "principal": principal_loan1,
        "interest": principal_loan1 // 10,
        "pro_rata": pro_rata,
        "lender": lender
    })
    signed_offer = sign_offer(offer, lender_key, p2p_nfts_eth.address)
    token_id = offer.collateral_min_token_id
    origination_fee = offer.origination_fee_amount

    bayc.mint(borrower, token_id)
    bayc.approve(p2p_nfts_eth.address, token_id, sender=borrower)
    weth.deposit(value=principal_loan1 - origination_fee, sender=lender)
    weth.approve(p2p_nfts_eth.address, principal_loan1, sender=lender)

    loan_id = p2p_nfts_eth.create_loan(signed_offer, token_id, borrower, sender=borrower)

    loan1 = Loan(
        id=loan_id,
        amount=offer.principal,
        interest=offer.interest,
        payment_token=offer.payment_token,
        maturity=now + offer.duration,
        start_time=now,
        borrower=borrower,
        lender=lender,
        collateral_contract=bayc.address,
        collateral_token_id=token_id,
        origination_fee_amount=offer.origination_fee_amount,
        broker_fee_bps=offer.broker_fee_bps,
        broker_address=offer.broker_address,
        protocol_fee_bps=p2p_nfts_eth.protocol_fee(),
        pro_rata=offer.pro_rata
    )
    assert compute_loan_hash(loan1) == p2p_nfts_eth.loans(loan_id)

    loan_duration = loan1.maturity - loan1.start_time
    actual_duration = loan_duration * 2 // 3
    interest = (loan1.interest * actual_duration // loan_duration) if offer.pro_rata else loan1.interest
    protocol_fee_amount = interest * loan1.protocol_fee_bps // 10000
    broker_fee_amount = interest * loan1.broker_fee_bps // 10000

    lender2, key2 = (lender, lender_key) if same_lender else (lender2, lender2_key)
    offer2 = Offer(**offer_bayc.offer._asdict() | {
        "principal": principal_loan2,
        "interest": principal_loan2 // 10,
        "lender": lender2,
        "expiration": offer.expiration + actual_duration
    })
    signed_offer2 = sign_offer(offer2, key2, p2p_nfts_eth.address)

    borrower_delta = offer2.principal - loan1.amount - offer2.origination_fee_amount - interest
    current_lender_delta = loan1.amount + interest - protocol_fee_amount - broker_fee_amount
    new_lender_delta = offer2.origination_fee_amount - offer2.principal

    print(f"{borrower=}, {lender=}, {lender2=}")
    print(f"{loan1.amount=}, {loan1.interest=}, {loan1.protocol_fee_bps=}, {loan1.broker_fee_bps=}")
    print(f"{offer2.principal=}, {offer2.origination_fee_amount=}")
    print(f"{actual_duration=}, {interest=}, {protocol_fee_amount=}, {broker_fee_amount=}")
    print(f"{borrower_delta=}, {current_lender_delta=}, {new_lender_delta=}")

    initial_borrower_balance = boa.env.get_balance(borrower)
    initial_lender_balance = boa.env.get_balance(lender)
    initial_lender2_balance = boa.env.get_balance(lender2)

    if lender != lender2:
        weth.deposit(value=-new_lender_delta, sender=lender2)
        weth.approve(p2p_nfts_eth.address, -new_lender_delta, sender=lender2)
    elif current_lender_delta + new_lender_delta < 0:
        lender_delta = current_lender_delta + new_lender_delta
        weth.deposit(value=-lender_delta, sender=lender)
        weth.approve(p2p_nfts_eth.address, -lender_delta, sender=lender)

    boa.env.time_travel(seconds=actual_duration)
    loan2_id = p2p_nfts_eth.replace_loan(loan1, signed_offer2, sender=borrower, value=max(0, -borrower_delta))

    loan2 = Loan(
        id=loan2_id,
        amount=offer2.principal,
        interest=offer2.interest,
        payment_token=offer2.payment_token,
        maturity=now + actual_duration + offer2.duration,
        start_time=now + actual_duration,
        borrower=borrower,
        lender=lender2,
        collateral_contract=bayc.address,
        collateral_token_id=token_id,
        origination_fee_amount=offer2.origination_fee_amount,
        broker_fee_bps=offer2.broker_fee_bps,
        broker_address=offer2.broker_address,
        protocol_fee_bps=p2p_nfts_eth.protocol_fee(),
        pro_rata=offer2.pro_rata
    )
    assert compute_loan_hash(loan2) == p2p_nfts_eth.loans(loan2_id)

    assert boa.env.get_balance(borrower) == initial_borrower_balance + borrower_delta
    if lender != lender2:
        assert boa.env.get_balance(lender) == initial_lender_balance + current_lender_delta
        assert boa.env.get_balance(lender2) == initial_lender2_balance + new_lender_delta
    else:
        assert boa.env.get_balance(lender) == initial_lender_balance + new_lender_delta + current_lender_delta
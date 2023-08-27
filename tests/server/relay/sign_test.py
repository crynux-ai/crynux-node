from h_server import relay


def test_sign():
    signer = relay.Signer("0x420fcabfd5dbb55215490693062e6e530840c64de837d071f0d9da21aaac861e")
    timestamp, signature = signer.sign(
        {"task_id": 1},
        timestamp=1692446475
    )

    expected = "0xdd78a14f5dcef6a57c5cfba8466baa1ac0ad2767e52eaf5a409895742e0475b4402acacaed2a2d7f158eac2f39849d653b45f207b0204858114cd38c415de5c700"
    assert signature == expected

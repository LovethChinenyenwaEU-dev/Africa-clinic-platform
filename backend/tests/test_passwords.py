from app.modules.identity.passwords import hash_password, verify_password


def test_correct_password_is_accepted():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_wrong_password_is_rejected():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_same_password_gives_different_hashes():
    first = hash_password("same-password")
    second = hash_password("same-password")
    assert first != second
    assert verify_password("same-password", first) is True
    assert verify_password("same-password", second) is True


def test_hash_does_not_contain_the_password():
    assert "same-password" not in hash_password("same-password")


def test_damaged_hash_is_rejected_without_crashing():
    assert verify_password("anything", "not-a-real-hash") is False
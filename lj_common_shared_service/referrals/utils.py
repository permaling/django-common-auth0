from uuid import uuid4


def generate_referral_code():
    return str(uuid4())[:-30]

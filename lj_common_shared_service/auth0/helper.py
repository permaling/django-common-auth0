from __future__ import unicode_literals

__author__ = 'David Baum'

from auth0.v3 import authentication
import json, jwt, logging, requests
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import authenticate

from lj_common_shared_service.auth0.settings import AUTH0_SETTINGS

logger = logging.getLogger(__name__)


def get_auth0_client_access_token() -> str:
    auth0_domain = AUTH0_SETTINGS.get("AUTH0_DOMAIN")
    client_id = AUTH0_SETTINGS.get('AUTH0_KEY')
    client_secret = AUTH0_SETTINGS.get('AUTH0_SECRET')
    audience = AUTH0_SETTINGS.get('AUTH0_AUDIENCE')
    auth0_get_token = authentication.GetToken(domain=auth0_domain)
    client_credentials = auth0_get_token.client_credentials(
        client_id=client_id,
        client_secret=client_secret,
        audience=audience
    )

    if client_credentials and client_credentials.get('access_token'):
        access_token = client_credentials.get('access_token')
        return access_token
    logger.error(f'An error occurred while getting the Auth0 client credentials: {client_credentials}')
    return None


def jwt_get_username_from_payload_handler(payload):
    if payload:
        username = payload.get('sub').replace('|', '.')
        authenticate(remote_user=username)
        return username
    return None


def jwt_decode_token(token):
    header = jwt.get_unverified_header(token)
    auth0_domain = AUTH0_SETTINGS.get("AUTH0_DOMAIN")
    auth0_domain = urlparse(auth0_domain).netloc
    if not auth0_domain:
        auth0_domain = AUTH0_SETTINGS.get("AUTH0_DOMAIN")

    jwks = requests.get(
        f'https://{auth0_domain}/.well-known/jwks.json',
        timeout=10
    ).json()
    public_key = None

    for jwk in jwks['keys']:
        if jwk['kid'] == header['kid']:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

    if public_key is None:
        logger.error(f'Auth0 Public key not found in {jwk}.')
        return None

    issuer = f'https://{auth0_domain}/'

    JWT_ALGORITHM = getattr(settings, 'JWT_ALGORITHM', 'RS256')
    JWT_AUTH = getattr(settings, 'JWT_AUTH', None)
    if JWT_AUTH and JWT_ALGORITHM in JWT_AUTH:
        JWT_ALGORITHM = JWT_AUTH.get('JWT_ALGORITHM', JWT_ALGORITHM)

    try:
        decoded_token = jwt.decode(
            token,
            public_key,
            audience=AUTH0_SETTINGS.get("AUTH0_AUDIENCE"),
            issuer=issuer,
            algorithms=[JWT_ALGORITHM]
        )

        decoded_token.update(
            token=token,
            domain=auth0_domain
        )

        return decoded_token
    except jwt.Exceptions.ExpiredSignatureError:
        logger.error(f'The Auth0 token {token} has an expired signature')
        return None

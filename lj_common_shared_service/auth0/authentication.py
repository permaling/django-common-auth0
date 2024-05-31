from __future__ import unicode_literals

__author__ = 'David Baum'

import logging
from multiprocessing import Process
from typing import List

from auth0.v3 import authentication, management
from auth0.v3.exceptions import Auth0Error

from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_jwt.authentication import JSONWebTokenAuthentication

from lj_common_shared_service.auth0.helper import get_auth0_client_access_token
from lj_common_shared_service.authentication.models import LJOrganization
from lj_common_shared_service.auth0.settings import AUTH0_USER_META_ENV
from lj_common_shared_service.referrals.models import ReferralCode, ReferralNode

User = get_user_model()

logger = logging.getLogger(__name__)


class LJJSONWebTokenAuthentication(JSONWebTokenAuthentication):

    def authenticate_credentials(self, payload):
        token = payload.get('token')
        auth0_domain = payload.get('domain')
        auth0_user_id = payload.get('sub')

        if token:
            db_user = self._get_db_user(auth0_user_id)
            if db_user:
                User.objects.filter(email=auth0_user_id.replace('|', '.')).delete()
                user = db_user
                self._set_user_auth0_data(user, auth0_user_id, payload)
            else:
                auth0_user_data = self._get_auth0_user_data(token, auth0_domain, auth0_user_id)
                if auth0_user_data:
                    user_metadata = auth0_user_data.get('user_metadata', dict())
                    email = auth0_user_data.get('email')
                    username = auth0_user_data.get('username')
                    name = auth0_user_data.get('name')

                    try:
                        user = User.objects.get(
                            email=email
                        )
                    except User.DoesNotExist:
                        raw_password = User.objects.make_random_password()
                        user = User.objects.create_user(email, raw_password)
                    self._set_user_auth0_data(user, auth0_user_id, payload)

                    referral_code = user_metadata.get("referral_code")
                    if referral_code is not None:
                        try:
                            referral_obj = ReferralCode.objects.get(code=referral_code)
                        except ReferralCode.DoesNotExist:
                            pass
                        else:
                            if referral_code.owner != user:
                                ReferralNode.objects.get_or_create(referral_code=referral_obj, referred=user)

                    organization_data = user_metadata.get(AUTH0_USER_META_ENV)
                    if organization_data is not None:
                        is_organization_admin = organization_data.get('is_organization_admin', False)
                        is_organization_editor = organization_data.get('is_organization_editor', False)
                        if not user.is_organization_admin:
                            user.is_organization_admin = is_organization_admin
                        if not user.is_organization_editor:
                            user.is_organization_editor = is_organization_editor

                        try:
                            organization_uuid = organization_data.get('organization_uuid')
                            organization = LJOrganization.objects.get(uuid=organization_uuid)
                            setattr(user, 'organization', organization)

                            user.organization = organization
                        except LJOrganization.DoesNotExist:
                            pass

                    user.auth0_user_id = auth0_user_id
                    if not user.username:
                        user.username = username
                        if name:
                            split_name = name.split()
                            if split_name and len(split_name) > 1 and len(split_name[1]) > 0:
                                user.username = f'{split_name[0]}{split_name[1][:1]}'
                    if not user.full_name:
                        user.full_name = name
                    user.save()

            linking_accounts_process = Process(
                target=self._resolve_accounts_linking,
                args=(user.email, auth0_domain, auth0_user_id,)
            )
            linking_accounts_process.start()

            setattr(user, 'token', token.decode('utf-8'))
        return user

    def _resolve_accounts_linking(self, email: str, auth0_domain: str, auth0_user_id: str):
        client_access_token = get_auth0_client_access_token()
        users_by_email = self._get_auth0_users_by_email(client_access_token, auth0_domain, email, auth0_user_id)
        if users_by_email and len(users_by_email) > 1:
            main_user_account = None

            for auth0_user in users_by_email:
                user_metadata = auth0_user.get('user_metadata')
                if user_metadata:
                    environment_data = user_metadata.get(AUTH0_USER_META_ENV)
                    if environment_data:
                        organization = environment_data.get('organization')
                        if organization:
                            main_user_account = auth0_user
                            break

            if main_user_account:
                main_user_account_identities = main_user_account.get('identities')
                for auth0_user in users_by_email:
                    user_id = auth0_user.get('user_id')
                    if user_id != main_user_account.get('user_id'):
                        is_identity_found = False
                        for identity in main_user_account_identities:
                            if identity.get('user_id') == user_id:
                                is_identity_found = True
                                break
                        if not is_identity_found:
                            auth0_user_identity = auth0_user.get('identities')[0]
                            auth0_users_manager = management.Users(domain=auth0_domain, token=client_access_token)
                            auth0_users_manager.link_user_account(
                                main_user_account.get('user_id'),
                                dict(
                                    provider=auth0_user_identity.get('provider'),
                                    user_id=user_id
                                )
                            )

    def _get_auth0_users_by_email(self, token: str, auth0_domain: str, email: str, exclude_auth0_user_id: str) -> List:
        auth0_users_manager = management.Users(domain=auth0_domain, token=token)
        query = f'email:"<%= "{email}" %>" AND email_verified:true -user_id:"<%= "{exclude_auth0_user_id}" %>"'
        data = auth0_users_manager.list(q=query)
        return data.get('users') if data else []

    def _get_auth0_user_data(self, token: str, auth0_domain: str, auth0_user_id: str):
        try:
            users = authentication.Users(auth0_domain)
            headers = {'Authorization': f"Bearer {token.decode('utf-8')}"}
            auth0_user_data_url = f'{users.protocol}://{users.domain}/api/v2/users/{auth0_user_id}'
            auth0_user_data = users.get(
                url=auth0_user_data_url,
                headers=headers
            )

            return auth0_user_data
        except Auth0Error as e:
            logger.error(f"An error occurred while fetching the user profile: {e}")
            raise AuthenticationFailed(_('Invalid token.'))

    def _get_db_user(self, auth0_user_id: str) -> User:
        try:
            return User.objects.get(auth0_user_id=auth0_user_id)
        except User.DoesNotExist:
            return None

    def _set_user_auth0_data(self, user: User, auth0_user_id: str, jwt_decoded_token: str):
        setattr(user, 'auth0_user_id', auth0_user_id)
        setattr(user, 'jwt_decoded_token', jwt_decoded_token)

from __future__ import unicode_literals

__author__ = 'David Baum'

import django
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.forms.fields import Field
from django.http import HttpRequest
from django.test import TransactionTestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_text
from django.utils.translation import ugettext as _

from .forms import LJUserCreationForm

try:
    from django.contrib.auth.middleware import SessionAuthenticationMiddleware
except ImportError:
    # Only available from Django 1.7, ignore the tests otherwise
    SessionAuthenticationMiddleware = None

try:
    from unittest import skipIf
except ImportError:
    # Only available from Python 2.7, import Django's bundled version otherwise
    from django.utils.unittest import skipIf


class UserTest(TransactionTestCase):
    user_email = 'newuser@localhost.local'
    user_password = '1234'

    def create_user(self):
        """Create and return a new user with self.user_email as login and self.user_password as password."""
        return get_user_model().objects.create_user(self.user_email, self.user_password)

    def test_user_creation(self):
        # Create a new user saving the time frame
        before_creation = timezone.now()
        self.create_user()
        after_creation = timezone.now()

        # Check user exists and email is correct
        self.assertEqual(get_user_model().objects.all().count(), 2)
        self.assertEqual(get_user_model().objects.all()[1].email, self.user_email)

        # Check date_joined, date_modified and last_login dates
        self.assertLess(before_creation, get_user_model().objects.all()[1].date_joined)
        self.assertLess(get_user_model().objects.all()[1].date_joined, after_creation)

        # User is just created, but not logged in yet
        self.assertIsNone(get_user_model().objects.all()[1].last_login)

        # Check flags
        self.assertTrue(get_user_model().objects.all()[1].is_active)
        self.assertFalse(get_user_model().objects.all()[1].is_staff)
        self.assertFalse(get_user_model().objects.all()[1].is_superuser)

    def test_user_get_full_name(self):
        user = self.create_user()
        # We didn't set the user's full name, so it should be NULL or None
        self.assertIsNone(user.get_full_name())

    def test_user_get_short_name(self):
        user = self.create_user()
        self.assertEqual(user.get_short_name(), self.user_email)

    def test_email_user(self):
        # Email definition
        subject = "Email Subject"
        message = "Email Message"
        from_email = 'from@normal.com'

        user = self.create_user()

        # Test that no message exists
        self.assertEqual(len(mail.outbox), 0)

        # Send test email
        user.email_user(subject, message, from_email)

        # Test that one message has been sent
        self.assertEqual(len(mail.outbox), 1)

        # Verify that the email is correct
        self.assertEqual(mail.outbox[0].subject, subject)
        self.assertEqual(mail.outbox[0].body, message)
        self.assertEqual(mail.outbox[0].from_email, from_email)
        self.assertEqual(mail.outbox[0].to, [user.email])

    def test_email_user_kwargs(self):
        # valid send_mail parameters
        kwargs = {
            "fail_silently": False,
            "auth_user": None,
            "auth_password": None,
            "connection": None,
        }
        user = get_user_model()(email='foo@bar.com')
        user.email_user(
            subject="Subject here",
            message="This is a message", from_email="from@domain.com", **kwargs)
        # Test that one message has been sent.
        self.assertEqual(len(mail.outbox), 1)
        # Verify that test email contains the correct attributes:
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Subject here")
        self.assertEqual(message.body, "This is a message")
        self.assertEqual(message.from_email, "from@domain.com")
        self.assertEqual(message.to, [user.email])


class UserManagerTest(TransactionTestCase):

    def test_create_user(self):
        email_lowercase = 'normal@normal.com'
        user = get_user_model().objects.create_user(email_lowercase)
        self.assertEqual(user.email, email_lowercase)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        email_lowercase = 'normal@normal.com'
        password = 'password1234$%&/'
        user = get_user_model().objects.create_superuser(email_lowercase, password)
        self.assertEqual(user.email, email_lowercase)
        self.assertTrue(user.check_password, password)
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_user_creation_is_active(self):
        # Create deactivated user
        email_lowercase = 'normal@normal.com'
        password = 'password1234$%&/'
        user = get_user_model().objects.create_user(email_lowercase, password, is_active=False)
        self.assertFalse(user.is_active)

    def test_user_creation_is_staff(self):
        # Create staff user
        email_lowercase = 'normal@normal.com'
        password = 'password1234$%&/'
        user = get_user_model().objects.create_user(email_lowercase, password, is_staff=True)
        self.assertTrue(user.is_staff)

    def test_create_user_email_domain_normalize_rfc3696(self):
        # According to http://tools.ietf.org/html/rfc3696#section-3
        # the "@" symbol can be part of the local part of an email address
        returned = get_user_model().objects.normalize_email(r'Abc\@DEF@EXAMPLE.com')
        self.assertEqual(returned, r'Abc\@DEF@example.com')

    def test_create_user_email_domain_normalize(self):
        returned = get_user_model().objects.normalize_email('normal@DOMAIN.COM')
        self.assertEqual(returned, 'normal@domain.com')

    def test_create_user_email_domain_normalize_with_whitespace(self):
        returned = get_user_model().objects.normalize_email('email\ with_whitespace@D.COM')
        self.assertEqual(returned, 'email\ with_whitespace@d.com')

    def test_empty_username(self):
        self.assertRaisesMessage(
            ValueError,
            'The given email must be set',
            get_user_model().objects.create_user, email=''
        )


@skipIf(SessionAuthenticationMiddleware is None, "SessionAuthenticationMiddleware not available in this version")
class TestSessionAuthenticationMiddleware(TransactionTestCase):

    def setUp(self):
        self.user_email = 'test@example.com'
        self.user_password = 'test_password'
        self.user = get_user_model().objects.create_user(
            self.user_email,
            self.user_password)

    def test_changed_password_invalidates_session(self):
        """Test that changing a user's password invalidates the session."""
        verification_middleware = SessionAuthenticationMiddleware()
        self.assertTrue(self.client.login(
            username=self.user_email,
            password=self.user_password,
        ))
        request = HttpRequest()
        request.session = self.client.session
        request.user = self.user
        verification_middleware.process_request(request)
        self.assertIsNotNone(request.user)
        self.assertFalse(request.user.is_anonymous())

        request.user.set_password('new_password')
        request.user.save()
        verification_middleware.process_request(request)
        self.assertIsNotNone(request.user)
        self.assertFalse(request.user.is_anonymous())


@override_settings(USE_TZ=False, PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',))
class LJUserCreationFormTest(TransactionTestCase):

    def setUp(self):
        get_user_model().objects.create_user('testclient@example.com', 'test123')

    def test_user_already_exists(self):
        data = {
            'email': 'testclient@example.com',
            'password1': 'test123',
            'password2': 'test123',
        }
        form = LJUserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form["email"].errors,
                         [force_text(form.error_messages['duplicate_email'])])

    def test_invalid_data(self):
        data = {
            'email': 'testclient',
            'password1': 'test123',
            'password2': 'test123',
        }
        form = LJUserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form["email"].errors,
                         [_('Enter a valid email address.')])

    def test_password_verification(self):
        # The verification password is incorrect.
        data = {
            'email': 'testclient@example.com',
            'password1': 'test123',
            'password2': 'test',
        }
        form = LJUserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form["password2"].errors,
                         [force_text(form.error_messages['password_mismatch'])])

    def test_both_passwords(self):
        # One (or both) passwords weren't given
        data = {'email': 'testclient@example.com'}
        form = LJUserCreationForm(data)
        required_error = [force_text(Field.default_error_messages['required'])]
        self.assertFalse(form.is_valid())
        self.assertEqual(form['password1'].errors, required_error)
        self.assertEqual(form['password2'].errors, required_error)

        data['password2'] = 'test123'
        form = LJUserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(form['password1'].errors, required_error)
        self.assertEqual(form['password2'].errors, [])

    def test_success(self):
        # The success case.
        data = {
            'email': 'jsmith@example.com',
            'password1': 'test123',
            'password2': 'test123',
        }
        form = LJUserCreationForm(data)
        self.assertTrue(form.is_valid())
        u = form.save()
        self.assertEqual(repr(u), '<%s: jsmith@example.com>' % get_user_model().__name__)


class LJUserAdminTest(TransactionTestCase):

    def setUp(self):
        self.user_email = 'test@example.com'
        self.user_password = 'test_password'
        self.user = get_user_model().objects.create_superuser(
            self.user_email,
            self.user_password)

        if settings.AUTH_USER_MODEL == "authentication.LJUser":
            self.app_name = "authentication"
            self.model_name = "ljuser"
            self.model_verbose_name = "user"
            self.model_verbose_name_plural = "Users"
            if django.VERSION[:2] < (1, 7):
                self.app_verbose_name = "User"
            else:
                self.app_verbose_name = "Users"
        elif settings.AUTH_USER_MODEL == "test_authentication_subclass.LJEmailUser":
            self.app_name = "test_authentication_subclass"
            self.model_name = "ljemailuser"
            self.model_verbose_name = "LJUserVerboseName"
            self.model_verbose_name_plural = "LJUserVerboseNamePlural"
            if django.VERSION[:2] < (1, 7):
                self.app_verbose_name = "Test_User_Subclass"
            else:
                self.app_verbose_name = "Test User Subclass"

    def test_url(self):
        self.assertTrue(self.client.login(
            username=self.user_email,
            password=self.user_password,
        ))
        response = self.client.get(reverse("admin:app_list", args=(self.app_name,)))
        self.assertEqual(response.status_code, 200)

    def test_model_name(self):
        self.assertTrue(self.client.login(
            username=self.user_email,
            password=self.user_password,
        ))

        response = self.client.get(reverse("admin:%s_%s_changelist" % (self.app_name, self.model_name)))
        self.assertEqual(force_text(response.context['title']), "Select %s to change" % self.model_verbose_name)

    def test_model_name_plural(self):
        self.assertTrue(self.client.login(
            username=self.user_email,
            password=self.user_password,
        ))

        response = self.client.get(reverse("admin:app_list", args=(self.app_name,)))
        self.assertEqual(force_text(response.context['app_list'][0]['models'][1]['name']),
                         self.model_verbose_name_plural)

from __future__ import unicode_literals

__author__ = 'David Baum'

import logging, requests, threading
from email.mime.image import MIMEImage
from typing import List

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import sanitize_address

from rest_framework import status


class ZohoEmailBackend(BaseEmailBackend):
    ZOHO_API_ENDPOINT = 'https://api.zeptomail.com'
    ZOHO_API_VERSION = 'v1.1'

    def __init__(self, api_key: str = None, from_name: str = None, fail_silently: bool = False, **kwargs):
        super(ZohoEmailBackend, self).__init__(fail_silently=fail_silently)
        self.api_key = api_key or settings.ZOHO_MAIL_API_KEY
        self.from_name = from_name or settings.DEFAULT_FROM_EMAIL_NAME
        self._lock = threading.RLock()

    def send_messages(self, email_messages):
        """
        Sends one or more EmailMessage objects and returns the number of email
        messages sent.
        """
        if not email_messages:
            return
        with self._lock:
            num_sent = 0
            for message in email_messages:
                sent = self._send(message)
                if sent:
                    num_sent += 1
        return num_sent

    def _send(self, email_message: EmailMessage):
        if not email_message.recipients():
            return False
        from_email = sanitize_address(email_message.from_email, email_message.encoding) or self.from_name
        recipients = ZohoEmailBackend.handle_recipients(email_message)
        cc_emails = ZohoEmailBackend.handle_carbon_copies(email_message)

        headers = {
            'Authorization': f'{self.api_key}',
            'Content-Type': 'application/json'
        }

        mail_data = {
            'from': dict(address=from_email, name=self.from_name),
            'to': recipients,
            'subject': email_message.subject,
            'htmlbody': ''.join(email_message.body.splitlines()),
            'bcc': [dict(email_address=dict(address=bcc)) for bcc in email_message.bcc],
            'inline_images': [],
            'reply_to': [dict(address=reply_to) for reply_to in email_message.reply_to]
        }

        if cc_emails:
            mail_data.update(
                cc=cc_emails
            )

        inline_images = ZohoEmailBackend.handle_attachments(email_message)
        if inline_images:
            mail_data.update(
                inline_images=inline_images
            )

        logging.info(f'Sending mail sent via the Zoho service to: {recipients}')

        response = requests.post(
            url=f'{self.ZOHO_API_ENDPOINT}/v1.1/email',
            json=mail_data,
            headers=headers,
            timeout=10000
        )
        response_data = response.json()

        if response.status_code != status.HTTP_201_CREATED:
            logging.error(f'An error occurred while mail send via the Zoho service: {response_data}')
            if not self.fail_silently:
                response.raise_for_status()
            return False

        logging.info(f'Successfully mail sent via the Zoho service: {response_data}')
        return True

    @staticmethod
    def handle_carbon_copies(email_message: EmailMessage) -> List[str]:
        cc_emails = []
        for cc_email in email_message.cc:
            cc_address = sanitize_address(cc_email, email_message.encoding)
            cc_data = dict(
                email_address=dict(
                    address=cc_address
                )
            )
            cc_emails.append(cc_data)
        return cc_emails

    @staticmethod
    def handle_recipients(email_message: EmailMessage) -> List[str]:
        recipients = []
        for recipient in email_message.recipients():
            recipient_address = sanitize_address(recipient, email_message.encoding)
            if recipient_address not in email_message.bcc and recipient_address not in email_message.cc:
                recipient_data = dict(
                    email_address=dict(
                        address=recipient_address
                    )
                )
                recipients.append(recipient_data)
        return recipients

    @staticmethod
    def handle_attachments(email_message: EmailMessage) -> List[str]:
        inline_images = []
        for attachment in (email_message.attachments or []):
            if isinstance(attachment, MIMEImage):

                attachment_headers = attachment._headers or []
                inline_image = dict(
                    content=attachment.get_payload().replace('\n', ''),
                    name="image.jpeg",
                    mime_type="image/jpeg"
                )

                inline_images.append(inline_image)
                for attachment_header in attachment_headers:
                    if attachment_header[0] == 'Content-Id':
                        inline_image.update(cid=attachment_header[1])
                    if attachment_header[0] == 'Content-Type':
                        inline_image.update(mime_type=attachment_header[1])
                    if attachment_header[0] == 'Content-Disposition':
                        filename = attachment_header[1].split('inline; filename=')[1]
                        inline_image.update(name=filename.replace('"', '').strip())
        return inline_images

from __future__ import unicode_literals

__author__ = 'David Baum'

from django.core.mail import EmailMultiAlternatives
from django.template import Context, Template
from django.utils.translation import ugettext_lazy as _

from django_mail_template.models import MailTemplate
from django_mail_template.tools import (replace_context_variable,
                                        clean_address_list)


class Mailer:
    @staticmethod
    def send_mail_template(mail_template: MailTemplate, context=None, attachments=[]):
        """
        When sending an email a set of attributes will be required.
        The required attributes are mainly dictated by django.core.mail
        used to send mail:
            * Message or body.
            * Subject.
            * Recipients list or to.
            * From email

        :param mail_template: is the mail template from the DB
        :param context: A dictionary with context variables to be used with
                        the subject and the message.
        :return: A tuple (result, message) where result is a boolean indicating
                if mail could be sent or not. A message in case the mail
                could not be sent the message will be the reason. This could
               have future uses if logging is implemented.
    """

        subject = mail_template.subject
        body = mail_template.body
        if context is None:
            # Needed whe no context is received so no replacement is tried.
            pass
        elif not isinstance(context, dict):
            raise ValueError(_('The argument for send method must be a '
                               'mapping.'))
        else:
            subject = replace_context_variable(text=mail_template.subject,
                                               context_variable=context)
            template = Template(mail_template.body)
            body = template.render(Context(context))
        msg = EmailMultiAlternatives(
            subject=subject,
            from_email=mail_template.from_email,
            to=clean_address_list(mail_template.to),
            cc=clean_address_list(mail_template.cc),
            bcc=clean_address_list(mail_template.bcc),
            reply_to=clean_address_list(mail_template.reply_to),
            attachments=attachments
        )
        msg.body = body
        msg.attach_alternative(body, 'text/html')
        return msg.send()

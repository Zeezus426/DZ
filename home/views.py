from django.shortcuts import render
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .forms import ContactForm


def home(request):
    """
    Home page view for AusTrade Commodities.
    Renders the main landing page with company information,
    commodities, trust badges, and global reach details.
    """
    contact_form = ContactForm()

    context = {
        'company_name': 'AusTrade Commodities',
        'page_title': 'Premium Australian Commodities Exporter',
        'contact_form': contact_form,
    }
    return render(request, 'home/home.html', context)


@csrf_exempt
def contact_submit(request):
    """
    Handle contact form submissions via AJAX.
    Validates the form and sends emails using django.core.mail.send_mail.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Invalid request method'
        }, status=405)

    form = ContactForm(request.POST)

    if not form.is_valid():
        return JsonResponse({
            'success': False,
            'errors': form.errors.get_json_data()
        }, status=400)

    # Extract cleaned data
    name = form.cleaned_data['name']
    email = form.cleaned_data['email']
    phone = form.cleaned_data.get('phone', 'Not provided')
    company = form.cleaned_data.get('company', 'Not provided')
    subject = form.cleaned_data['subject']
    message = form.cleaned_data['message']

    # Get the full subject text
    subject_choices = dict(form.fields['subject'].choices)
    full_subject = subject_choices.get(subject, subject)

    # Create email content for the company
    company_email_body = f"""
New Contact Form Submission

Name: {name}
Email: {email}
Phone: {phone}
Company: {company}
Subject: {full_subject}

Message:
{message}

---
This email was sent from the AusTrade Commodities website.
"""

    # Create email content for the visitor (auto-reply)
    visitor_email_body = f"""
Dear {name},

Thank you for contacting AusTrade Commodities.

We have received your inquiry regarding "{full_subject}" and our team will review it shortly. We typically respond within 1-2 business days.

Your inquiry details:
Subject: {full_subject}
Message: {message}

If you have any urgent matters, please call us at +61 2 8000 0000.

Best regards,
The AusTrade Commodities Team

---
AusTrade Commodities
Premium Australian Hard Coking Coal & Iron Ore Exporter
Sydney, Australia
info@austradecommodities.com
www.austradecommodities.com
"""

    try:
        # Send email to the company
        send_mail(
            subject=f'Website Contact: {full_subject} - {name}',
            message=company_email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.CONTACT_EMAIL],
            fail_silently=False,
        )

        # Send auto-reply to the visitor
        send_mail(
            subject='Thank you for contacting AusTrade Commodities',
            message=visitor_email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        return JsonResponse({
            'success': True,
            'message': 'Thank you for your message. We will get back to you soon!'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to send email: {str(e)}'
        }, status=500)


def about(request):
    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'error': 'Invalid request method'
        }, status=405)
    return render(request, 'home/about.html')

def certification(request):
    if request.method != 'GET':
        return JsonResponse({
            'success': False,
        })
    return render(request, 'home/certification.html')
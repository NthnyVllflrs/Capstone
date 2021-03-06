import geocoder
import threading

import cloudinary
import cloudinary.uploader
import cloudinary.api

from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .forms import *
from .utils import nearby_responder
from user.models import Reporter, Notification

cloudinary.config( 
  cloud_name = "nthnyvllflrs", 
  api_key = "751561493749527", 
  api_secret = "QmDSPjbnPlDTLCLuySiiA0wQg6s" 
)



from django import forms
from django.http import HttpResponse

from cloudinary.forms import cl_init_js_callbacks      
from .models import Photo
from .forms import PhotoForm

def upload(request):
  context = dict( backend_form = PhotoForm())

  if request.method == 'POST':
    form = PhotoForm(request.POST, request.FILES)
    context['posted'] = form.instance
    if form.is_valid():
        form.save()

  return render(request, 'report/upload.html', context)

@login_required
def report_create(request):

  is_reporter = Reporter.objects.filter(user=request.user).exists()
  if is_reporter and not request.user.reporter.activated:
    return redirect('report:report-timeline')

  if is_reporter or request.user.is_superuser:
    report_created, can_report = False, False
    time_threshold = datetime.now() - timedelta(minutes=5)
    
    reports = Report.objects.filter(reporter=request.user, timestamp__gte=time_threshold).order_by('-timestamp')
    results = Report.objects.filter(timestamp__gte=time_threshold).exclude(verifies=request.user).order_by('-timestamp')

    if not reports:
      can_report = True
    else:
      can_report = False

    if request.user.is_superuser:
      can_report = True

    if request.method == 'POST':
      form = ReportForm(request.POST, request.FILES)
      if form.is_valid():
        report = form.save(commit=False)
        
        report.reporter = request.user

        # Reverse GeoCoding
        latitude = float(report.latitude)
        longitude = float(report.longitude)
        location = geocoder.google([latitude, longitude], method='reverse', key=settings.GOOGLE_MAP_API_KEY)
        report.address = location.address

        report.save()

        t = threading.Thread(target=nearby_responder(report))
        t.setDaemon = True
        t.start()
        
        report_created = True

    else:
      if request.user.is_superuser:
        form = ReportForm(initial={
          'latitude': 6.9214,
          'longitude': 122.0790,
          'address': 'Veterans Ave, Zamboanga, Zamboanga del Sur, Philippines',
        })
      else:
        form = ReportForm(initial={
          'latitude': request.user.reporter.latitude,
          'longitude': request.user.reporter.longitude,
          'address': request.user.reporter.address,
        })

    context = {
      'form': form, 
      'report_created': report_created, 
      'can_report': can_report, 
      'results': results
    }

    return render(request, 'report/report-create.html', context) 
  else:
    return redirect('report:report-timeline')

@login_required
def report_timeline(request):

  is_reporter = Reporter.objects.filter(user=request.user).exists()
  if is_reporter and not request.user.reporter.activated:
    account_active = False
  else:
    account_active = True

  if account_active:
    object_list = Report.objects.filter(status='Ongoing').order_by('-timestamp')
    object_list_2 = Report.objects.filter(status='Cleared').order_by('-timestamp')[:6]

    if request.is_ajax():
      return render(request, 'report/report-timeline-ajax.html', {'object_list': object_list, 'object_list_2': object_list_2})

    return render(request, 'report/report-timeline.html', {'account_active': account_active, 'object_list': object_list, 'object_list_2': object_list_2})
  
  return render(request,'report/report-timeline.html', {'account_active': account_active})

@login_required
def report_detail(request, pk):

  is_reporter = Reporter.objects.filter(user=request.user).exists()
  if is_reporter and not request.user.reporter.activated:
    return redirect('report:report-timeline')

  _object = get_object_or_404(Report, pk=pk)

  if is_reporter or request.user.is_superuser:
    return render(request, 'report/report-detail-reporter.html', {'object': _object})
  else:
    is_responder = Notification.objects.filter(report=_object, recipient=request.user).exists()
    return render(request, 'report/report-detail-responder.html', {'object': _object, 'is_responder': is_responder})

@login_required
def report_cleared(request):

  is_reporter = Reporter.objects.filter(user=request.user).exists()
  if is_reporter and not request.user.reporter.activated:
    return redirect('report:report-timeline')

  object_list = Report.objects.filter(status='Cleared').order_by('-timestamp')

  return render(request,'report/report-cleared.html', {'object_list': object_list})
from django.shortcuts import render
import json # Used to safely dump Python lists into JavaScripts
from django.http import HttpResponse
from django.contrib.auth import authenticate, login



# def index(request):
#     print("Calling index")
#     return HttpResponse("Hello, world. .")


def apigee_dynamic_chart_view(request):
    data = {
        'apigee_start': 10,
        'apigee_stop': 20,
        'apigee_status': 40
    }
    # 1. Extract Labels and Data
    labels = list(data.keys())   # ['apigee_start', 'apigee_stop', 'apigee_status']
    values = list(data.values()) # [10, 20, 40]

    # 2. Use json.dumps to safely convert Python lists/dict to JSON strings
    context = {
        # These are passed to the template and will be parsed by JavaScript
        'chart_labels_json': json.dumps(labels),
        'chart_values_json': json.dumps(values),
    }
    return render(request, 'apigee_chart_js_template.html', context)


def login_view(request):
    if request.method == "POST":
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Django-auth-ldap intercepts this and checks AD
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            login(request, user)
            return JsonResponse({"status": "success", "redirect": "/dashboard/"})
        else:
            return JsonResponse({"status": "error", "message": "Invalid AD Credentials"}, status=401)
            
    return render(request, 'index.html')
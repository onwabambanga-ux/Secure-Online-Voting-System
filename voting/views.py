from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, F
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator
import pandas as pd
from django.db import transaction

from .forms import RegistrationForm, ProfileUpdateForm, StudentImportForm
from .models import Election, Candidate, StudentProfile, Vote, AuditLog


def home(request):
    return render(request, 'voting/home.html')


def user_login(request):
    if request.user.is_authenticated and request.method == 'GET':
        if request.user.is_staff:
            return redirect('admin_dashboard')
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            
            AuditLog.objects.create(
                user=user,
                action='LOGIN',
                description=f'User {user.username} logged in'
            )

            if user.is_staff:
                return redirect('admin_dashboard')

            return redirect('dashboard')

        return render(
            request,
            'voting/login.html',
            {'error': 'Invalid username or password.'}
        )

    return render(request, 'voting/login.html')


def register(request):
    if request.user.is_authenticated and request.method == 'GET':
        if request.user.is_staff:
            return redirect('admin_dashboard')
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            
            AuditLog.objects.create(
                user=user,
                action='REGISTER',
                description=f'User {user.username} registered'
            )
            
            messages.success(
                request,
                'Your account has been created successfully!'
            )

            return redirect('dashboard')

    else:
        form = RegistrationForm()

    return render(
        request,
        'voting/register.html',
        {'form': form}
    )


@login_required(login_url='login')
def user_logout(request):
    AuditLog.objects.create(
        user=request.user,
        action='LOGOUT',
        description=f'User {request.user.username} logged out'
    )
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required(login_url='login')
def dashboard(request):
    elections = Election.objects.all().order_by('start_date')
    
    for election in elections:
        election.update_status()

    voted_election_ids = Vote.objects.filter(
        voter=request.user
    ).values_list(
        'election_id',
        flat=True
    )
    
    try:
        student_profile = request.user.student_profile
    except StudentProfile.DoesNotExist:
        student_profile = None

    return render(
        request,
        'voting/dashboard.html',
        {
            'elections': elections,
            'voted_election_ids': voted_election_ids,
            'student_profile': student_profile,
        }
    )


@login_required(login_url='login')
def vote(request, election_id):

    election = get_object_or_404(
        Election,
        id=election_id
    )

    election.update_status()

    if election.status != 'OPEN':
        messages.error(
            request,
            'This election is not currently open for voting.'
        )
        return redirect('dashboard')

    # Check student profile
    try:
        student_profile = request.user.student_profile

    except StudentProfile.DoesNotExist:
        messages.error(
            request,
            'Your student profile could not be found.'
        )
        return redirect('dashboard')

    # Check registration
    if not student_profile.registered:
        messages.error(
            request,
            'You are not registered and cannot vote.'
        )
        return redirect('dashboard')

    # Check eligibility
    if not student_profile.eligible:
        messages.error(
            request,
            'You are not eligible to vote.'
        )
        return redirect('dashboard')

    # Check account status
    if student_profile.account_status != 'ACTIVE':
        messages.error(
            request,
            'Your account is not active.'
        )
        return redirect('dashboard')

    # Check whether the voter has already completed
    # both sections of this election
    institutional_vote = Vote.objects.filter(
        voter=request.user,
        election=election,
        src_category='INSTITUTIONAL'
    ).exists()

    campus_vote = Vote.objects.filter(
        voter=request.user,
        election=election,
        src_category='CAMPUS'
    ).exists()

    if institutional_vote and campus_vote:
        messages.error(
            request,
            'You have already voted in this election.'
        )
        return redirect('dashboard')

    # Pass partial-voting state to the template so it can hide
    # whichever section the voter has already completed, and only
    # show the section(s) still open to them.
    already_voted_institutional = institutional_vote
    already_voted_campus = campus_vote    
 
    # Get candidates separately
    institutional_candidates = election.candidates.filter(
        src_category='INSTITUTIONAL'
    )

    campus_candidates = election.candidates.filter(
        src_category='CAMPUS'
    )

    # Process submitted votes
    if request.method == 'POST':

        institutional_candidate_id = request.POST.get(
            'institutional_candidate'
        )

        campus_candidate_id = request.POST.get(
            'campus_candidate'
        )

        # A category is only required if this voter hasn't
        # already cast a ballot in it.
        if not already_voted_institutional and not institutional_candidate_id:
            messages.error(
                request,
                'Please select one Institutional SRC candidate.'
            )
            return redirect(
                'vote',
                election_id=election.id
            )

        if not already_voted_campus and not campus_candidate_id:
            messages.error(
                request,
                'Please select one Campus SRC candidate.'
            )
            return redirect(
                'vote',
                election_id=election.id
            )
        
        # Only look up a candidate for a category the voter hasn't
        # already voted in. already_voted_* being True means these
        # stay None and nothing gets created for that category below.
        institutional_candidate = None
        campus_candidate = None

        if not already_voted_institutional:
            # Make sure the Institutional candidate
            # actually belongs to this election and category
            institutional_candidate = get_object_or_404(
                Candidate,
                id=institutional_candidate_id,
                election=election,
                src_category='INSTITUTIONAL'
            )

        if not already_voted_campus:
            # Make sure the Campus candidate
            # actually belongs to this election and category
            campus_candidate = get_object_or_404(
                Candidate,
                id=campus_candidate_id,
                election=election,
                src_category='CAMPUS'
            )
        
        # Save only the vote category/categories that have not
        # already been completed by this voter.
        with transaction.atomic():

            if not already_voted_institutional:
                Vote.objects.create(
                    voter=request.user,
                    election=election,
                    candidate=institutional_candidate,
                    src_category='INSTITUTIONAL'
                )

            if not already_voted_campus:
                Vote.objects.create(
                    voter=request.user,
                    election=election,
                    candidate=campus_candidate,
                    src_category='CAMPUS'
                )

        if already_voted_institutional:
            messages.success(
                request,
                'Your Campus SRC vote has been successfully recorded.'
            )
        elif already_voted_campus:
            messages.success(
                request,
                'Your Institutional SRC vote has been successfully recorded.'
            )
        else:
            messages.success(
                request,
                'Your Institutional SRC and Campus SRC votes have been successfully recorded.'
            )

        return redirect('dashboard')

    # Display voting page
    return render(
        request,
        'voting/vote.html',
        {
            'election': election,
            'institutional_candidates': institutional_candidates,
            'campus_candidates': campus_candidates,
            'already_voted_institutional': already_voted_institutional,
            'already_voted_campus': already_voted_campus,
        }
    )

@login_required(login_url='login')
def results(request):

    elections = Election.objects.all().order_by('-end_date')

    for election in elections:
        election.update_status()

    results_data = []

    for election in elections:

        if election.status not in ['SCHEDULED', 'DRAFT']:

            institutional_candidates = election.candidates.filter(
                src_category='INSTITUTIONAL'
            )

            campus_candidates = election.candidates.filter(
                src_category='CAMPUS'
            )

            # Institutional SRC results
            institutional_results = []

            institutional_total_votes = Vote.objects.filter(
                election=election,
                src_category='INSTITUTIONAL'
            ).count()

            for candidate in institutional_candidates:

                vote_count = Vote.objects.filter(
                    election=election,
                    candidate=candidate,
                    src_category='INSTITUTIONAL'
                ).count()

                if institutional_total_votes > 0:
                    percentage = round(
                        (vote_count / institutional_total_votes) * 100,
                        2
                    )
                else:
                    percentage = 0

                institutional_results.append({
                    'candidate': candidate,
                    'vote_count': vote_count,
                    'percentage': percentage,
                    'is_winner': False,
                })

            # Find Institutional SRC winner
            if institutional_results:

                max_votes = max(
                    result['vote_count']
                    for result in institutional_results
                )

                for result in institutional_results:

                    if (
                        result['vote_count'] == max_votes
                        and max_votes > 0
                    ):
                        result['is_winner'] = True


            # Campus SRC results
            campus_results = []

            campus_total_votes = Vote.objects.filter(
                election=election,
                src_category='CAMPUS'
            ).count()

            for candidate in campus_candidates:

                vote_count = Vote.objects.filter(
                    election=election,
                    candidate=candidate,
                    src_category='CAMPUS'
                ).count()

                if campus_total_votes > 0:
                    percentage = round(
                        (vote_count / campus_total_votes) * 100,
                        2
                    )
                else:
                    percentage = 0

                campus_results.append({
                    'candidate': candidate,
                    'vote_count': vote_count,
                    'percentage': percentage,
                    'is_winner': False,
                })

            # Find Campus SRC winner
            if campus_results:

                max_votes = max(
                    result['vote_count']
                    for result in campus_results
                )

                for result in campus_results:

                    if (
                        result['vote_count'] == max_votes
                        and max_votes > 0
                    ):
                        result['is_winner'] = True


            results_data.append({
                'election': election,

                'institutional_results': institutional_results,
                'institutional_total_votes': institutional_total_votes,

                'campus_results': campus_results,
                'campus_total_votes': campus_total_votes,
            })

        else:

            results_data.append({
                'election': election,

                'institutional_results': [],
                'institutional_total_votes': 0,

                'campus_results': [],
                'campus_total_votes': 0,
            })


    return render(
        request,
        'voting/results.html',
        {
            'elections': results_data,
        }
    )

@login_required(login_url='login')
def profile(request):
    try:
        student_profile = request.user.student_profile
    except StudentProfile.DoesNotExist:
        student_profile = None
        messages.warning(request, 'Your student profile has not been set up yet.')

    total_elections = Election.objects.count()
    elections_voted = Vote.objects.filter(voter=request.user).count()
    pending_elections = Election.objects.filter(
        status='OPEN'
    ).exclude(
        id__in=Vote.objects.filter(voter=request.user).values_list('election_id', flat=True)
    ).count()

    return render(
        request,
        'voting/profile.html',
        {
            'user': request.user,
            'student_profile': student_profile,
            'total_elections': total_elections,
            'elections_voted': elections_voted,
            'pending_elections': pending_elections,
        }
    )


@login_required(login_url='login')
def edit_profile(request):
    try:
        student_profile = request.user.student_profile
    except StudentProfile.DoesNotExist:
        messages.error(request, 'Student profile not found.')
        return redirect('profile')

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=student_profile)
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=student_profile)

    return render(
        request,
        'voting/edit_profile.html',
        {'form': form}
    )


# ========================
# ADMIN VIEWS
# ========================

@login_required(login_url='login')
def admin_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if not request.user.is_staff:
        return redirect('dashboard')

    total_elections = Election.objects.count()
    total_candidates = Candidate.objects.count()
    total_voters = User.objects.filter(is_staff=False).count()

    return render(
        request,
        'voting/admin_dashboard.html',
        {
            'total_elections': total_elections,
            'total_candidates': total_candidates,
            'total_voters': total_voters,
        }
    )


@login_required(login_url='login')
def manage_elections(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if not request.user.is_staff:
        return redirect('dashboard')

    elections = Election.objects.all().order_by('-id')

    return render(
        request,
        'voting/manage_elections.html',
        {
            'elections': elections,
        }
    )


@login_required(login_url='login')
def create_election(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if not request.user.is_staff:
        return redirect('dashboard')

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        status = request.POST.get('status')
        election_type = request.POST.get(
            'election_type',
            'INSTITUTIONAL'
        )
        campus = request.POST.get('campus', '')

        # Create election and candidates together
        with transaction.atomic():

            election = Election.objects.create(
                title=title,
                description=description,
                start_date=start_date,
                end_date=end_date,
                status=status,
                election_type=election_type,
                campus=campus if campus else None
            )

            # Get the number of candidates submitted
            candidate_count = int(
                request.POST.get('candidate_count', 0)
            )

            # Create each candidate
            for i in range(candidate_count):

                candidate_name = request.POST.get(
                    f'candidate_name_{i}'
                )

                candidate_type = request.POST.get(
                    f'candidate_type_{i}'
                )
                candidate_src_category = request.POST.get(
                    f'candidate_src_category_{i}'
           
                )

                candidate_description = request.POST.get(
                    f'candidate_description_{i}',
                    ''
                )

                candidate_image = request.FILES.get(
                    f'candidate_image_{i}'
                )

                # Only create a candidate if a name was provided
                if candidate_name:

                    Candidate.objects.create(
                        election=election,
                        name=candidate_name,
                        candidate_type=candidate_type,
                        src_category=candidate_src_category,
                        description=candidate_description,
                        image=candidate_image
                    )

            AuditLog.objects.create(
                user=request.user,
                action='CREATE_ELECTION',
                description=f'Created election: {election.title}'
            )

        messages.success(
            request,
            f'Election "{title}" has been created successfully!'
        )

        return redirect('manage_elections')

    return render(
        request,
        'voting/create_election.html'
    )


@login_required(login_url='login')
def edit_election(request, election_id):
    if not request.user.is_authenticated:
        return redirect('login')

    if not request.user.is_staff:
        return redirect('dashboard')

    election = get_object_or_404(Election, id=election_id)

    if request.method == 'POST':
        election.title = request.POST.get('title', election.title)
        election.description = request.POST.get('description', election.description)
        election.start_date = request.POST.get('start_date', election.start_date)
        election.end_date = request.POST.get('end_date', election.end_date)
        election.status = request.POST.get('status', election.status)
        election.election_type = request.POST.get('election_type', election.election_type)
        election.campus = request.POST.get('campus', election.campus)
        election.save()
        
        AuditLog.objects.create(
            user=request.user,
            action='EDIT_ELECTION',
            description=f'Edited election: {election.title}'
        )

        messages.success(
            request,
            f'Election "{election.title}" has been updated successfully!'
        )

        return redirect('manage_elections')

    return render(
        request,
        'voting/edit_election.html',
        {'election': election}
    )


@login_required(login_url='login')
def delete_election(request, election_id):
    if not request.user.is_authenticated:
        return redirect('login')

    if not request.user.is_staff:
        return redirect('dashboard')

    election = get_object_or_404(Election, id=election_id)
    
    if request.method == 'POST':
        title = election.title
        election.delete()
        
        AuditLog.objects.create(
            user=request.user,
            action='DELETE_ELECTION',
            description=f'Deleted election: {title}'
        )
        
        messages.success(
            request,
            f'Election "{title}" has been deleted successfully!'
        )
        
        return redirect('manage_elections')

    return render(
        request,
        'voting/delete_election.html',
        {'election': election}
    )


@login_required(login_url='login')
def import_students(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if not request.user.is_staff:
        return redirect('dashboard')

    if request.method == 'POST':
        form = StudentImportForm(request.POST, request.FILES)
        
        if form.is_valid():
            excel_file = request.FILES['excel_file']
            
            try:
                df = pd.read_excel(excel_file)
                
                required_columns = ['Student Number', 'Full Name', 'Campus', 'Faculty']
                missing_columns = [col for col in required_columns if col not in df.columns]
                
                if missing_columns:
                    messages.error(
                        request,
                        f'Missing required columns: {", ".join(missing_columns)}'
                    )
                    return render(request, 'voting/import_students.html', {'form': form})
                
                success_count = 0
                error_count = 0
                errors = []
                
                for index, row in df.iterrows():
                    try:
                        student_number = str(row['Student Number']).strip()
                        full_name = str(row['Full Name']).strip()
                        campus = str(row['Campus']).strip()
                        faculty = str(row['Faculty']).strip()
                        
                        registered = str(row.get('Registered', 'TRUE')).upper() in ['TRUE', 'YES', '1', 'Y']
                        eligible = str(row.get('Eligible', 'TRUE')).upper() in ['TRUE', 'YES', '1', 'Y']
                        account_status = str(row.get('Account Status', 'ACTIVE')).upper()
                        
                        if account_status not in ['ACTIVE', 'SUSPENDED', 'INACTIVE']:
                            account_status = 'ACTIVE'
                        
                        student, created = StudentProfile.objects.update_or_create(
                            student_number=student_number,
                            defaults={
                                'full_name': full_name,
                                'campus': campus,
                                'faculty': faculty,
                                'registered': registered,
                                'eligible': eligible,
                                'account_status': account_status
                            }
                        )
                        
                        success_count += 1
                            
                    except Exception as e:
                        error_count += 1
                        errors.append(f"Row {index + 2}: {str(e)}")
                
                AuditLog.objects.create(
                    user=request.user,
                    action='IMPORT_STUDENTS',
                    description=f'Imported {success_count} students, {error_count} errors'
                )
                
                if success_count > 0:
                    messages.success(
                        request,
                        f'Successfully imported {success_count} students!'
                    )
                
                if error_count > 0:
                    messages.warning(
                        request,
                        f'{error_count} rows had errors. Check the logs for details.'
                    )
                
                if errors:
                    for error in errors[:5]:
                        messages.error(request, error)
                
                return redirect('admin_dashboard')
                
            except Exception as e:
                messages.error(
                    request,
                    f'Error reading file: {str(e)}'
                )
                return render(request, 'voting/import_students.html', {'form': form})
    
    else:
        form = StudentImportForm()
    
    return render(request, 'voting/import_students.html', {'form': form})


@login_required(login_url='login')
def view_audit_logs(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if not request.user.is_staff:
        return redirect('dashboard')

    # Get all audit logs, ordered by most recent first
    audit_logs = AuditLog.objects.all().order_by('-timestamp')
    
    # Filter by action type if provided
    action_filter = request.GET.get('action', '')
    if action_filter:
        audit_logs = audit_logs.filter(action=action_filter)
    
    # Filter by user if provided
    user_filter = request.GET.get('user', '')
    if user_filter:
        audit_logs = audit_logs.filter(user__username__icontains=user_filter)
    
    # Get unique actions for filter dropdown
    unique_actions = AuditLog.objects.values_list('action', flat=True).distinct().order_by('action')
    
    # Get all users for filter dropdown
    users = User.objects.all().order_by('username')
    
    return render(
        request,
        'voting/audit_logs.html',
        {
            'audit_logs': audit_logs,
            'unique_actions': unique_actions,
            'users': users,
            'action_filter': action_filter,
            'user_filter': user_filter,
        }
    )

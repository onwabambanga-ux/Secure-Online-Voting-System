from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, F
from django.http import HttpResponse, HttpResponseForbidden
from django.core.paginator import Paginator
import pandas as pd
from django.db import transaction, IntegrityError
from .forms import RegistrationForm, ProfileUpdateForm, StudentImportForm
from .models import Election, Candidate, StudentProfile, Vote, VoterReceipt, AuditLog
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

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

    voted_election_ids = VoterReceipt.objects.filter(
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
    institutional_vote = VoterReceipt.objects.filter(
        voter=request.user,
        election=election,
        src_category='INSTITUTIONAL'
    ).exists()

    campus_vote = VoterReceipt.objects.filter(
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

        # Both selections are required
        if not institutional_candidate_id:
            messages.error(
                request,
                'Please select one Institutional SRC candidate.'
            )
            return redirect(
                'vote',
                election_id=election.id
            )

        if not campus_candidate_id:
            messages.error(
                request,
                'Please select one Campus SRC candidate.'
            )
            return redirect(
                'vote',
                election_id=election.id
            )

        # Make sure the Institutional candidate
        # actually belongs to this election and category
        institutional_candidate = get_object_or_404(
            Candidate,
            id=institutional_candidate_id,
            election=election,
            src_category='INSTITUTIONAL'
        )

        # Make sure the Campus candidate
        # actually belongs to this election and category
        campus_candidate = get_object_or_404(
            Candidate,
            id=campus_candidate_id,
            election=election,
            src_category='CAMPUS'
        )

        # Save both voting records together.
        # VoterReceipt identifies that the student voted.
        # Vote stores only the anonymous ballot choice.
        try:
            with transaction.atomic():

                # Institutional SRC receipt
                VoterReceipt.objects.create(
                    voter=request.user,
                    election=election,
                    src_category='INSTITUTIONAL'
                )

                # Institutional anonymous ballot
                Vote.objects.create(
                    election=election,
                    candidate=institutional_candidate,
                    src_category='INSTITUTIONAL'
                )

                # Campus SRC receipt
                VoterReceipt.objects.create(
                    voter=request.user,
                    election=election,
                    src_category='CAMPUS'
                )

                # Campus anonymous ballot
                Vote.objects.create(
                    election=election,
                    candidate=campus_candidate,
                    src_category='CAMPUS'
                )

                AuditLog.objects.create(
                    user=request.user,
                    action='VOTE_CAST',
                    description=(
                        f'Voter cast Institutional and Campus SRC ballots '
                        f'in election "{election.title}".'
                    )
                )

        except IntegrityError:
            messages.error(
                request,
                'You have already voted in one or both categories for this election.'
            )
            return redirect('dashboard')

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
    elections_voted = VoterReceipt.objects.filter(voter=request.user).values('election_id').distinct().count()
    pending_elections = Election.objects.filter(
        status='OPEN'
    ).exclude(
        id__in=VoterReceipt.objects.filter(voter=request.user).values_list('election_id', flat=True)
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

    # Voting statistics
    total_votes = Vote.objects.count()

    students_voted = VoterReceipt.objects.values('voter').distinct().count()

    students_not_voted = max(
        total_voters - students_voted,
        0
    )

    if total_voters > 0:
        voting_percentage = round(
            (students_voted / total_voters) * 100,
            2
        )
    else:
        voting_percentage = 0

    return render(
        request,
        'voting/admin_dashboard.html',
        {
            'total_elections': total_elections,
            'total_candidates': total_candidates,
            'total_voters': total_voters,
            'total_votes': total_votes,
            'students_voted': students_voted,
            'students_not_voted': students_not_voted,
            'voting_percentage': voting_percentage,
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
@login_required(login_url='login')
def export_results_excel(request):
    if not request.user.is_staff:
        return redirect('dashboard')

    # ---------------------------------------------------------
    # 1. ELECTION SUMMARY
    # ---------------------------------------------------------

    elections = Election.objects.all().order_by('-end_date')

    summary_data = []

    for election in elections:

        election.update_status()

        eligible_students = StudentProfile.objects.filter(
            registered=True,
            eligible=True,
            account_status='ACTIVE'
        ).count()

        students_voted = VoterReceipt.objects.filter(
            election=election
        ).values('voter').distinct().count()

        students_not_voted = max(
            eligible_students - students_voted,
            0
        )

        participation = (
            round((students_voted / eligible_students) * 100, 2)
            if eligible_students > 0
            else 0
        )

        institutional_votes = Vote.objects.filter(
            election=election,
            src_category='INSTITUTIONAL'
        ).count()

        campus_votes = Vote.objects.filter(
            election=election,
            src_category='CAMPUS'
        ).count()

        summary_data.append({
            'Election': election.title,
            'Election Type': election.get_election_type_display(),
            'Campus': election.campus or 'All Campuses',
            'Status': election.get_status_display(),
            'Start Date': election.start_date.strftime(
                '%Y-%m-%d %H:%M'
            ),
            'End Date': election.end_date.strftime(
                '%Y-%m-%d %H:%M'
            ),
            'Eligible Students': eligible_students,
            'Students Who Voted': students_voted,
            'Students Not Voted': students_not_voted,
            'Participation (%)': participation,
            'Institutional Votes': institutional_votes,
            'Campus Votes': campus_votes,
        })

    summary_df = pd.DataFrame(summary_data)

    # ---------------------------------------------------------
    # 2. CANDIDATE RESULTS
    # ---------------------------------------------------------

    candidate_data = []

    for election in elections:

        for category in ['INSTITUTIONAL', 'CAMPUS']:

            candidates = election.candidates.filter(
                src_category=category
            )

            total_category_votes = Vote.objects.filter(
                election=election,
                src_category=category
            ).count()

            candidate_votes = []

            for candidate in candidates:

                vote_count = Vote.objects.filter(
                    election=election,
                    candidate=candidate,
                    src_category=category
                ).count()

                percentage = (
                    round(
                        (vote_count / total_category_votes) * 100,
                        2
                    )
                    if total_category_votes > 0
                    else 0
                )

                candidate_votes.append({
                    'candidate': candidate,
                    'vote_count': vote_count,
                    'percentage': percentage,
                })

            max_votes = max(
                [item['vote_count'] for item in candidate_votes],
                default=0
            )

            for item in candidate_votes:

                candidate_data.append({
                    'Election': election.title,
                    'SRC Category': category,
                    'Candidate': item['candidate'].name,
                    'Candidate Type':
                        item['candidate'].get_candidate_type_display(),
                    'Votes': item['vote_count'],
                    'Percentage (%)': item['percentage'],
                    'Result':
                        'Winner'
                        if item['vote_count'] == max_votes
                        and max_votes > 0
                        else ''
                })

    candidate_df = pd.DataFrame(candidate_data)

    # ---------------------------------------------------------
    # 3. CAMPUS STATISTICS
    # ---------------------------------------------------------

    campus_data = []

    campuses = StudentProfile.objects.values_list(
        'campus',
        flat=True
    ).distinct().order_by('campus')

    for campus in campuses:

        if not campus:
            continue

        eligible = StudentProfile.objects.filter(
            campus=campus,
            registered=True,
            eligible=True,
            account_status='ACTIVE'
        ).count()

        student_numbers = StudentProfile.objects.filter(
            campus=campus,
            registered=True,
            eligible=True,
            account_status='ACTIVE'
        ).values_list(
            'user_id',
            flat=True
        )

        voted = VoterReceipt.objects.filter(
            voter_id__in=student_numbers
        ).values('voter').distinct().count()

        not_voted = max(
            eligible - voted,
            0
        )

        participation = (
            round((voted / eligible) * 100, 2)
            if eligible > 0
            else 0
        )

        campus_data.append({
            'Campus': campus,
            'Eligible Students': eligible,
            'Students Who Voted': voted,
            'Students Not Voted': not_voted,
            'Participation (%)': participation,
        })

    campus_df = pd.DataFrame(campus_data)

    # ---------------------------------------------------------
    # 4. FACULTY STATISTICS
    # ---------------------------------------------------------

    faculty_data = []

    faculties = StudentProfile.objects.values_list(
        'faculty',
        flat=True
    ).distinct().order_by('faculty')

    for faculty in faculties:

        if not faculty:
            continue

        eligible = StudentProfile.objects.filter(
            faculty=faculty,
            registered=True,
            eligible=True,
            account_status='ACTIVE'
        ).count()

        student_numbers = StudentProfile.objects.filter(
            faculty=faculty,
            registered=True,
            eligible=True,
            account_status='ACTIVE'
        ).values_list(
            'user_id',
            flat=True
        )

        voted = VoterReceipt.objects.filter(
            voter_id__in=student_numbers
        ).values('voter').distinct().count()

        not_voted = max(
            eligible - voted,
            0
        )

        participation = (
            round((voted / eligible) * 100, 2)
            if eligible > 0
            else 0
        )

        faculty_data.append({
            'Faculty': faculty,
            'Eligible Students': eligible,
            'Students Who Voted': voted,
            'Students Not Voted': not_voted,
            'Participation (%)': participation,
        })

    faculty_df = pd.DataFrame(faculty_data)

    # ---------------------------------------------------------
    # 5. RESPONSE
    # ---------------------------------------------------------

    response = HttpResponse(
        content_type=(
            'application/vnd.openxmlformats-officedocument'
            '.spreadsheetml.sheet'
        )
    )

    response['Content-Disposition'] = (
        'attachment; filename="SRC_Voting_Report.xlsx"'
    )

    with pd.ExcelWriter(
        response,
        engine='openpyxl'
    ) as writer:

        summary_df.to_excel(
            writer,
            index=False,
            sheet_name='Election Summary'
        )

        candidate_df.to_excel(
            writer,
            index=False,
            sheet_name='Candidate Results'
        )

        campus_df.to_excel(
            writer,
            index=False,
            sheet_name='Campus Statistics'
        )

        faculty_df.to_excel(
            writer,
            index=False,
            sheet_name='Faculty Statistics'
        )

    return response

@login_required(login_url='login')
def export_results_pdf(request):
    if not request.user.is_staff:
        return redirect('dashboard')

    response = HttpResponse(content_type='application/pdf')

    response['Content-Disposition'] = (
        'attachment; filename="SRC_Voting_Report.pdf"'
    )

    pdf = canvas.Canvas(response, pagesize=A4)

    width, height = A4

    # ---------------------------------------------------------
    # Helper function for page breaks
    # ---------------------------------------------------------

    def check_page(y_position):
        if y_position < 60:
            pdf.showPage()
            return height - 50
        return y_position

    # ---------------------------------------------------------
    # REPORT HEADER
    # ---------------------------------------------------------

    y = height - 50

    pdf.setFont('Helvetica-Bold', 20)
    pdf.drawString(
        50,
        y,
        'Live SRC Voting System'
    )

    y -= 30

    pdf.setFont('Helvetica-Bold', 15)
    pdf.drawString(
        50,
        y,
        'Election Report'
    )

    y -= 25

    pdf.setFont('Helvetica', 9)
    pdf.drawString(
        50,
        y,
        f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'
    )

    y -= 35

    # ---------------------------------------------------------
    # OVERALL STATISTICS
    # ---------------------------------------------------------

    eligible_students = StudentProfile.objects.filter(
        registered=True,
        eligible=True,
        account_status='ACTIVE'
    ).count()

    students_voted = VoterReceipt.objects.values(
        'voter'
    ).distinct().count()

    students_not_voted = max(
        eligible_students - students_voted,
        0
    )

    participation = (
        round(
            (students_voted / eligible_students) * 100,
            2
        )
        if eligible_students > 0
        else 0
    )

    institutional_votes = Vote.objects.filter(
        src_category='INSTITUTIONAL'
    ).count()

    campus_votes = Vote.objects.filter(
        src_category='CAMPUS'
    ).count()

    pdf.setFont('Helvetica-Bold', 13)
    pdf.drawString(
        50,
        y,
        'Overall Voting Statistics'
    )

    y -= 25

    pdf.setFont('Helvetica', 10)

    statistics = [
        f'Eligible Students: {eligible_students}',
        f'Students Who Voted: {students_voted}',
        f'Students Not Voted: {students_not_voted}',
        f'Participation: {participation}%',
        f'Institutional SRC Votes: {institutional_votes}',
        f'Campus SRC Votes: {campus_votes}',
    ]

    for item in statistics:

        y = check_page(y)

        pdf.drawString(60, y, item)

        y -= 18

    y -= 15

    # ---------------------------------------------------------
    # ELECTION INFORMATION
    # ---------------------------------------------------------

    elections = Election.objects.all().order_by('-end_date')

    pdf.setFont('Helvetica-Bold', 13)
    pdf.drawString(
        50,
        y,
        'Elections'
    )

    y -= 25

    for election in elections:

        y = check_page(y)

        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(
            60,
            y,
            election.title[:60]
        )

        y -= 17

        pdf.setFont('Helvetica', 9)

        pdf.drawString(
            70,
            y,
            f'Type: {election.get_election_type_display()}'
        )

        y -= 15

        pdf.drawString(
            70,
            y,
            f'Status: {election.get_status_display()}'
        )

        y -= 15

        pdf.drawString(
            70,
            y,
            f'Campus: {election.campus or "All Campuses"}'
        )

        y -= 15

        pdf.drawString(
            70,
            y,
            f'Start: {election.start_date.strftime("%Y-%m-%d %H:%M")}'
        )

        y -= 15

        pdf.drawString(
            70,
            y,
            f'End: {election.end_date.strftime("%Y-%m-%d %H:%M")}'
        )

        y -= 25

    # ---------------------------------------------------------
    # CANDIDATE RESULTS
    # ---------------------------------------------------------

    pdf.setFont('Helvetica-Bold', 13)
    pdf.drawString(
        50,
        y,
        'Candidate Results'
    )

    y -= 25

    elections = Election.objects.all().order_by('-end_date')

    for election in elections:

        for category in ['INSTITUTIONAL', 'CAMPUS']:

            candidates = election.candidates.filter(
                src_category=category
            )

            if not candidates.exists():
                continue

            y = check_page(y)

            pdf.setFont('Helvetica-Bold', 11)
            pdf.drawString(
                60,
                y,
                f'{election.title[:35]} - {category}'
            )

            y -= 18

            total_category_votes = Vote.objects.filter(
                election=election,
                src_category=category
            ).count()

            candidate_results = []

            for candidate in candidates:

                vote_count = Vote.objects.filter(
                    election=election,
                    candidate=candidate,
                    src_category=category
                ).count()

                percentage = (
                    round(
                        (vote_count / total_category_votes) * 100,
                        2
                    )
                    if total_category_votes > 0
                    else 0
                )

                candidate_results.append({
                    'name': candidate.name,
                    'votes': vote_count,
                    'percentage': percentage,
                })

            max_votes = max(
                [
                    result['votes']
                    for result in candidate_results
                ],
                default=0
            )

            pdf.setFont('Helvetica', 9)

            for result in candidate_results:

                y = check_page(y)

                result_label = ''

                if (
                    result['votes'] == max_votes
                    and max_votes > 0
                ):
                    result_label = ' - Winner'

                pdf.drawString(
                    70,
                    y,
                    (
                        f'{result["name"][:35]}'
                        f' | Votes: {result["votes"]}'
                        f' | {result["percentage"]}%'
                        f'{result_label}'
                    )
                )

                y -= 16

            y -= 10

    # ---------------------------------------------------------
    # CAMPUS STATISTICS
    # ---------------------------------------------------------

    y = check_page(y)

    pdf.setFont('Helvetica-Bold', 13)
    pdf.drawString(
        50,
        y,
        'Campus Statistics'
    )

    y -= 25

    campuses = StudentProfile.objects.values_list(
        'campus',
        flat=True
    ).distinct().order_by('campus')

    for campus in campuses:

        if not campus:
            continue

        eligible = StudentProfile.objects.filter(
            campus=campus,
            registered=True,
            eligible=True,
            account_status='ACTIVE'
        ).count()

        user_ids = StudentProfile.objects.filter(
            campus=campus,
            registered=True,
            eligible=True,
            account_status='ACTIVE'
        ).values_list(
            'user_id',
            flat=True
        )

        voted = VoterReceipt.objects.filter(
            voter_id__in=user_ids
        ).values('voter').distinct().count()

        not_voted = max(
            eligible - voted,
            0
        )

        campus_participation = (
            round(
                (voted / eligible) * 100,
                2
            )
            if eligible > 0
            else 0
        )

        y = check_page(y)

        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(
            60,
            y,
            campus
        )

        y -= 16

        pdf.setFont('Helvetica', 9)

        pdf.drawString(
            70,
            y,
            f'Eligible: {eligible}'
        )

        y -= 14

        pdf.drawString(
            70,
            y,
            f'Voted: {voted}'
        )

        y -= 14

        pdf.drawString(
            70,
            y,
            f'Not Voted: {not_voted}'
        )

        y -= 14

        pdf.drawString(
            70,
            y,
            f'Participation: {campus_participation}%'
        )

        y -= 22

    # ---------------------------------------------------------
    # FACULTY STATISTICS
    # ---------------------------------------------------------

    y = check_page(y)

    pdf.setFont('Helvetica-Bold', 13)
    pdf.drawString(
        50,
        y,
        'Faculty Statistics'
    )

    y -= 25

    faculties = StudentProfile.objects.values_list(
        'faculty',
        flat=True
    ).distinct().order_by('faculty')

    for faculty in faculties:

        if not faculty:
            continue

        eligible = StudentProfile.objects.filter(
            faculty=faculty,
            registered=True,
            eligible=True,
            account_status='ACTIVE'
        ).count()

        user_ids = StudentProfile.objects.filter(
            faculty=faculty,
            registered=True,
            eligible=True,
            account_status='ACTIVE'
        ).values_list(
            'user_id',
            flat=True
        )

        voted = VoterReceipt.objects.filter(
            voter_id__in=user_ids
        ).values('voter').distinct().count()

        not_voted = max(
            eligible - voted,
            0
        )

        faculty_participation = (
            round(
                (voted / eligible) * 100,
                2
            )
            if eligible > 0
            else 0
        )

        y = check_page(y)

        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(
            60,
            y,
            faculty[:60]
        )

        y -= 16

        pdf.setFont('Helvetica', 9)

        pdf.drawString(
            70,
            y,
            f'Eligible: {eligible}'
        )

        y -= 14

        pdf.drawString(
            70,
            y,
            f'Voted: {voted}'
        )

        y -= 14

        pdf.drawString(
            70,
            y,
            f'Not Voted: {not_voted}'
        )

        y -= 14

        pdf.drawString(
            70,
            y,
            f'Participation: {faculty_participation}%'
        )

        y -= 22

    # ---------------------------------------------------------
    # FOOTER
    # ---------------------------------------------------------

    y = check_page(y)

    pdf.setFont('Helvetica-Oblique', 8)

    pdf.drawString(
        50,
        y,
        'This report contains aggregated voting statistics and '
        'does not reveal individual voter choices.'
    )

    pdf.save()

    return response

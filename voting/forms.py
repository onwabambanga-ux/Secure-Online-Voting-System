from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .models import StudentProfile, Candidate


class RegistrationForm(UserCreationForm):

    student_number = forms.CharField(
        max_length=50,
        required=True,
        label='Student Number'
    )

    email = forms.EmailField(
        required=True
    )

    class Meta:
        model = User
        fields = [
            'student_number',
            'username',
            'email',
            'password1',
            'password2',
        ]

    def clean_student_number(self):
        student_number = self.cleaned_data['student_number'].strip()

        try:
            student = StudentProfile.objects.get(
                student_number=student_number
            )
        except StudentProfile.DoesNotExist:
            raise forms.ValidationError(
                'Student number was not found in the official student records.'
            )

        if not student.registered:
            raise forms.ValidationError(
                'You are not currently registered and cannot create a voting account.'
            )

        if student.account_status != 'ACTIVE':
            raise forms.ValidationError(
                'Your student account is not active.'
            )

        if student.user_id is not None:
            raise forms.ValidationError(
                'An account already exists for this student.'
            )

        return student_number

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'An account with this email already exists.'
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            
            # Link student profile to user
            student_number = self.cleaned_data['student_number']
            student = StudentProfile.objects.get(student_number=student_number)
            student.user = user
            student.save()
            
        return user


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ['student_number', 'full_name', 'campus', 'faculty']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make student_number read-only
        if self.instance.pk:
            self.fields['student_number'].widget.attrs['readonly'] = True


class StudentImportForm(forms.Form):
    excel_file = forms.FileField(
        label='Select Excel File',
        help_text='Upload an .xlsx file with student details'
    )
class CandidateForm(forms.ModelForm):

    class Meta:
        model = Candidate
        fields = [
            'src_category',
            'campus',
            'candidate_type',
            'name',
            'description',
            'image',
        ]

        widgets = {
            'src_category': forms.Select(attrs={
                'class': 'form-control'
            }),

            'campus': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter campus for Campus SRC candidate'
            }),

            'candidate_type': forms.Select(attrs={
                'class': 'form-control'
            }),

            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Candidate or organization name'
            }),

            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Short description (optional)'
            }),

            'image': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }
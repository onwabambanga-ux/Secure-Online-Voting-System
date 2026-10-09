# Live SRC Voting System

A secure, web-based voting platform designed to support Student Representative Council (SRC) elections. The system enables eligible students to register, authenticate, cast anonymous votes, and view election results. Administrators can manage elections, candidates, official student records, results, and audit logs.

**Live application:** https://live-src-voting-system.onrender.com

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Objectives](#objectives)
3. [Features](#features)
4. [Election Types](#election-types)
5. [System Architecture](#system-architecture)
6. [Algorithms and Voting Workflow](#algorithms-and-voting-workflow)
7. [Database and Data Models](#database-and-data-models)
8. [Security and Privacy](#security-and-privacy)
9. [Technology Stack](#technology-stack)
10. [Installation and Setup](#installation-and-setup)
11. [Environment Configuration](#environment-configuration)
12. [Running the Application](#running-the-application)
13. [Testing](#testing)
14. [Excel and PDF Reports](#excel-and-pdf-reports)
15. [Deployment](#deployment)
16. [Project Structure](#project-structure)
17. [Limitations and Future Improvements](#limitations-and-future-improvements)

---

## Project Overview

The Live SRC Voting System is a Django-based web application developed to support Institutional SRC and Campus SRC elections.

The application verifies students against an official student list before allowing them to register and vote. Election opening and closing times are managed by administrators, and voting results can be displayed while an election is open.

The system separates voter participation records from anonymous ballots. This allows it to track whether a student has voted without storing the student's identity directly on the ballot.

The application is designed for use across multiple campuses and supports organizational and independent candidates.

## Objectives

The main objectives are to:

- Provide an accessible online voting platform for SRC elections.
- Verify student details against an official student list.
- Restrict voting to registered, eligible, active students.
- Prevent duplicate voting within the same election category.
- Support Institutional SRC and Campus SRC voting.
- Allow administrators to schedule and manage elections.
- Provide transparent election results and statistical reports.
- Maintain audit records of important administrative and user activities.
- Support anonymous ballot storage.
- Provide Excel and PDF result exports.
- Support secure password-reset and transactional email workflows.

## Features

### Student Features

- Student account registration.
- Login and logout.
- Eligibility and account-status verification.
- Student profile management.
- Access to available elections.
- Institutional SRC and Campus SRC voting.
- Campus-specific candidate filtering.
- Prevention of duplicate voting.
- Election results and live result updates where enabled.
- Password-reset requests and confirmation emails.

### Election Management

Administrators can:

- Create and manage elections.
- Configure election start and end times.
- Associate elections with campuses.
- Manage election statuses.
- Add candidates when creating an election.
- Upload election logos.
- Manage Institutional SRC and Campus SRC candidates.
- Create runoff elections and manually select their candidates.
- View election results and statistics.

The system restricts certain administrative operations, including student imports, while elections are scheduled or open.

### Student Management

Administrators can import official student records using an Excel workbook.

The current import format supports these columns:

- `Student Number`
- `Name`
- `Surname`
- `Campus`
- `Faculty`

Optional columns include:

- `University Email`
- `Registered`
- `Eligible`
- `Account Status`

The current import implementation calculates eligibility from registration status and account status. The `University Email` column is not currently saved by the import function, and the `Eligible` column does not override the calculated eligibility.

The system supports the following account statuses:

- `ACTIVE`
- `SUSPENDED`
- `INACTIVE`

Supported campus values are:

- `Alice Campus`
- `East London Campus`

### Candidate Management

Candidates belong to specific elections and can be categorized as:

- Organizations
- Independent candidates

Candidate records support descriptions, images, SRC categories, and campus associations where applicable.

### Election Results and Reporting

The results functionality includes:

- Candidate vote totals.
- Candidate vote percentages.
- Institutional and campus result breakdowns.
- Voting participation statistics.
- Campus statistics.
- Faculty statistics.
- Excel report export.
- PDF report export.
- Automatic column sizing and readable headings in exported Excel reports.

### Administrative Dashboard

The administrative dashboard provides access to:

- Manage Elections
- Import Students
- View Results
- Export Results (Excel)
- Export Results (PDF)
- Manage Voters
- View Audit Logs

Access to administrative functions is restricted to authorized staff accounts.

---

## Election Types

The system supports the following election configurations:

### Institutional SRC

Students select an eligible Institutional SRC candidate.

### Campus SRC

Students select a Campus SRC candidate associated with their own campus.

### Runoff

A runoff election is created manually by an administrator. The administrator configures the election and selects the candidates who will participate.

For the configured voting workflow, a student selects an Institutional SRC candidate and a Campus SRC candidate. The system validates both selections and records the ballots and participation receipts in one database transaction.

---

## System Architecture

The application follows a client-server architecture.

```text
                  Student / Administrator
                           |
                           v
                    Web Browser
                 HTML / CSS / JavaScript
                           |
                         HTTPS
                           |
                           v
                   Django Application
                  Authentication and Views
                           |
              +------------+-------------+
              |            |             |
              v            v             v
          Elections      Voting      Administration
              |            |             |
              +------------+-------------+
                           |
                           v
                     Django ORM
                           |
                           v
                    PostgreSQL
                   Production DB

External services:
- Brevo: transactional email delivery
- Cloudinary: election logos and candidate images
- Render: application hosting
- WhiteNoise: static file serving
```

The application uses Django's ORM to interact with the configured relational database. Local development may use MySQL, while the deployed application uses PostgreSQL.

---

## Algorithms and Voting Workflow

The system applies validation and decision-making algorithms throughout registration, login, voting, and result calculation.

### Student Eligibility Verification

1. Receive the student's registration details.
2. Locate the student in the official student records.
3. Check registration status.
4. Check eligibility.
5. Check account status.
6. Allow registration or login only when the relevant conditions are satisfied.

### Voting Algorithm

1. Authenticate the student.
2. Verify that the student's account is registered, eligible, and active.
3. Verify that the election is open.
4. Check whether the student has already voted in each relevant category.
5. Retrieve the valid Institutional SRC and campus-specific candidates.
6. Validate the submitted candidate selections.
7. Start a database transaction.
8. Create the voter participation receipts.
9. Store the anonymous ballots.
10. Record the corresponding audit event.
11. Commit the transaction.
12. Display confirmation and attempt to send a notification email.

If validation fails, the system rejects the submission. The transaction ensures that the paired voting records are not partially saved.

### Result Calculation

The system counts anonymous ballots associated with an election and candidate, calculates vote totals and percentages, and presents the results in the relevant categories.

### Eligibility Rule

The current student import logic calculates eligibility as:

`Eligible = Registered AND Account Status is ACTIVE`

The value supplied in the optional `Eligible` Excel column does not override this calculation.

---

## Database and Data Models

The system uses Django models to represent the main entities and relationships.

| Model | Purpose |
|---|---|
| `StudentProfile` | Student number, name, surname, campus, faculty, registration, eligibility, account status, and optional linked user |
| `Election` | Election details, type, campus, schedule, status, and optional logo |
| `Candidate` | Candidate name, description, image, category, campus, and associated election |
| `Vote` | Anonymous ballot containing the election, selected candidate, category, and timestamp |
| `VoterReceipt` | Records whether a voter has participated in an election category |
| `AuditLog` | Records important user and administrative activities |

### Anonymous Voting Design

The `Vote` model does not store a direct voter foreign key. The `VoterReceipt` model separately records participation and prevents a student from voting more than once in the same election category.

The receipt and ballot records are created together during the voting transaction.

This design separates voter participation tracking from the selected candidate. It does not, by itself, guarantee complete anonymity against every possible form of correlation or privileged database access.

---

## Security and Privacy

Security-related controls include:

- Django authentication and password hashing.
- Staff-only administrative views.
- Student registration verification.
- Eligibility and account-status checks.
- Server-side candidate validation.
- Prevention of duplicate voting by category.
- Anonymous ballot storage without a direct voter foreign key.
- Database transactions for paired ballot submissions.
- Audit logging.
- CSRF protection in Django forms.
- Scheduled election controls.
- Password-reset token workflows.
- Generic responses for password-reset requests to reduce account enumeration.
- Environment variables for deployment configuration and credentials.
- HTTPS through the production hosting platform.

**Security note:** The system implements these application-level controls, but production readiness also requires independent security testing, review of access permissions, database backups, monitoring, and verification of deployment settings.

---

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application programming language |
| Django | Web framework, authentication, routing, and ORM |
| HTML | Page structure |
| CSS | Styling and responsive layout |
| JavaScript | Client-side interactions |
| MySQL | Supported local development database |
| PostgreSQL | Production relational database |
| Pandas | Reading and processing Excel data |
| OpenPyXL | Excel workbook generation and formatting |
| ReportLab | PDF report generation |
| Pillow | Image processing support |
| Brevo API | Transactional email delivery |
| Cloudinary | Media storage for election logos and candidate images |
| WhiteNoise | Static file serving |
| Gunicorn | Production WSGI server |
| Render | Application hosting and deployment |
| Git and GitHub | Version control and source-code hosting |

---

## Installation and Setup

### Prerequisites

Install the following:

- Python version compatible with the project's dependencies.
- Git.
- MySQL for local development, if using the configured local MySQL database.
- A code editor such as Visual Studio Code.

### 1. Clone the Repository

```powershell
git clone https://github.com/onwabambanga-ux/Secure-Online-Voting-System.git
cd Secure-Online-Voting-System
```

### 2. Create a Virtual Environment

```powershell
python -m venv venv
```

Activate it in Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use an approved local execution-policy approach or activate the environment through your IDE.

### 3. Install Dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a local `.env` file in the project root. Configure the values required by your current `settings.py`, including:

- Django secret key.
- Debug mode.
- Allowed hosts.
- Database connection.
- Brevo API key and sender details.
- Cloudinary credentials.

Use the actual variable names expected by your settings. Do not commit `.env` to GitHub.

### 5. Apply Database Migrations

```powershell
python manage.py migrate
```

### 6. Create an Administrator

```powershell
python manage.py createsuperuser
```

Follow the prompts to configure the administrator account.

### 7. Check the Configuration

```powershell
python manage.py check
```

---

## Environment Configuration

The deployed application requires the environment variables used by the project's settings and build process.

These include the following categories:

| Category | Configuration |
|---|---|
| Django | `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` |
| Database | `DATABASE_URL` |
| Email | Brevo API key and sender configuration |
| Media | Cloudinary cloud name, API key, and API secret |
| Deployment administrator | Superuser username, email, and password variables used by the build script |

Use the exact variable names configured in the repository. Store credentials in local environment files or the hosting provider's environment-variable settings.

Never publish API keys, database passwords, Django secret keys, or administrator passwords in source code or documentation.

---

## Running the Application

Start the development server:

```powershell
python manage.py runserver
```

Open the local development address shown in the terminal, normally:

`http://127.0.0.1:8000/`

The administrator can then configure elections, import student records, manage candidates, and view reports.

---

## Testing

Before committing changes, run:

```powershell
python manage.py check
```

Apply migrations when models change:

```powershell
python manage.py makemigrations
python manage.py migrate
```

Important manual test scenarios include:

- Eligible student registration and login.
- Rejection of unregistered or ineligible accounts.
- Rejection of suspended or inactive accounts.
- Rejection of duplicate voting attempts.
- Validation of Institutional SRC and campus-specific selections.
- Election opening, closing, and deletion restrictions.
- Blocking student imports while elections are scheduled or open.
- Importing student records with separate `Name` and `Surname` columns.
- Excel and PDF report generation.
- Password-reset email delivery and generic responses for unrecognized accounts.
- Candidate image and election logo uploads.
- Verification that anonymous ballots do not contain a direct voter reference.

A successful Django system check verifies application configuration but is not a substitute for running the functional and security tests above.

---

## Excel and PDF Reports

The system provides separate export formats for election reporting.

### Excel

The results workbook contains four worksheets:

1. `Election Summary`
2. `Candidate Results`
3. `Campus Statistics`
4. `Faculty Statistics`

The export code automatically sizes columns according to their contents, bolds the headings, and freezes the first row.

### PDF

The system also provides PDF export functionality for election reports.

---

## Deployment

The production application is hosted on Render.

**Live application:** https://live-src-voting-system.onrender.com

The deployment setup uses:

- Render web service hosting.
- PostgreSQL for the production database.
- Gunicorn to serve the Django application.
- WhiteNoise for static files.
- Cloudinary for media storage.
- Brevo for transactional email.
- Environment variables for production configuration.
- A build script to install dependencies, collect static files, apply migrations, and optionally create an administrator when the required environment variables are provided.

Before deploying changes:

1. Run the Django system check.
2. Apply and test database migrations locally.
3. Verify that all required environment variables are configured.
4. Commit and push the changes to the configured GitHub branch.
5. Confirm that the Render deployment completes successfully.
6. Test critical features on the live application.

---

## Project Structure

The project contains the main Django project package and the voting application.

```text
Secure-Online-Voting-System/
├── manage.py
├── requirements.txt
├── README.md
├── .gitignore
├── online_voting/
│   ├── settings.py
│   ├── urls.py
│   └── build.sh
└── voting/
    ├── models.py
    ├── views.py
    ├── forms.py
    ├── urls.py
    ├── admin.py
    ├── migrations/
    ├── templates/
    └── static/
```

Additional configuration files and directories may exist in the repository.

---

## Limitations and Future Improvements

Potential areas for further development include:

- Automated unit, integration, and end-to-end tests.
- Independent security review and penetration testing.
- Stronger monitoring and alerting.
- Documented database backup and recovery procedures.
- Improved audit-log review and retention policies.
- Further verification of anonymous-voting guarantees.
- More comprehensive accessibility testing.
- Automated deployment checks and regression testing.

---

## Project Information

**Project:** Live SRC Voting System  
**Repository:** https://github.com/onwabambanga-ux/Secure-Online-Voting-System  
**Production hosting:** Render

This project is intended to support transparent and accessible SRC election administration through a web-based voting platform.
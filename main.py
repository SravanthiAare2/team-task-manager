from flask import Flask, render_template, request, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    UserMixin,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

# ================= CONFIG =================
app.config['SECRET_KEY'] = 'team-task-manager-secret'

import os
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    "DATABASE_URL",
    "sqlite:///taskmanager.db"
)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)
# ================= ADMIN =================
ALLOWED_ADMIN_EMAILS = ["admin@gmail.com", "admin1@gmail.com"]

# ================= LOGIN =================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# ================= MODELS =================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    role = db.Column(db.String(20), nullable=False)


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    credential_type = db.Column(db.String(100))
    credential_value = db.Column(db.String(300))
    start_date = db.Column(db.String(50))
    end_date = db.Column(db.String(50))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(100))
    due_date = db.Column(db.String(100))
    assigned_to = db.Column(db.String(100))
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ================= HOME =================
@app.route('/')
def home():
    return render_template('home.html')


# ================= REGISTER =================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':

        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']

        if User.query.filter_by(email=email).first():
            flash("Email already exists")
            return redirect('/register')

        if password != confirm_password:
            flash("Passwords do not match")
            return redirect('/register')

        if role == "admin" and email not in ALLOWED_ADMIN_EMAILS:
            flash("You are not allowed to register as admin")
            return redirect('/register')

        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            role=role
        )

        db.session.add(user)
        db.session.commit()

        flash("Registration successful")
        return redirect('/login')

    return render_template('register.html')


# ================= LOGIN =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful")

            if user.role == "admin":
                return redirect('/admin_dashboard')
            return redirect('/dashboard')

        flash("Invalid credentials")

    return render_template('login.html')


# ================= MEMBER DASHBOARD =================
@app.route('/dashboard')
@login_required
def dashboard():

    total_tasks = Task.query.filter_by(user_id=current_user.id).count()
    completed_tasks = Task.query.filter_by(user_id=current_user.id, status='Completed').count()
    pending_tasks = Task.query.filter_by(user_id=current_user.id, status='Pending').count()
    projects_count = Project.query.filter_by(user_id=current_user.id).count()

    tasks = Task.query.filter_by(user_id=current_user.id).all()
    projects = Project.query.filter_by(user_id=current_user.id).all()

    return render_template(
        'dashboard.html',
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
        projects_count=projects_count,
        tasks=tasks,
        projects=projects
    )


# ================= PROJECT DETAIL =================
@app.route('/project/<int:project_id>')
@login_required
def project_detail(project_id):

    project = Project.query.get_or_404(project_id)

    if current_user.role != "admin" and project.user_id != current_user.id:
        flash("Access denied")
        return redirect('/dashboard')

    tasks = Task.query.filter_by(project_id=project.id).all()

    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == "Completed"])

    progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    return render_template(
        "project_detail.html",
        project=project,
        tasks=tasks,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        progress=progress
    )


# ================= TASK DETAIL (NEW FIX) =================
@app.route('/task/<int:task_id>')
@login_required
def task_detail(task_id):

    task = Task.query.get_or_404(task_id)

    if current_user.role != "admin" and task.user_id != current_user.id:
        flash("Access denied")
        return redirect('/dashboard')

    project = Project.query.get(task.project_id)

    return render_template(
        "task_detail.html",
        task=task,
        project=project
    )


# ================= ADMIN DASHBOARD =================
@app.route('/admin_dashboard')
@login_required
def admin_dashboard():

    if current_user.role != "admin":
        flash("Access denied")
        return redirect('/dashboard')

    users = User.query.all()
    projects = db.session.query(Project, User.email).join(User, Project.user_id == User.id).all()
    tasks = db.session.query(Task, User.email).join(User, Task.user_id == User.id).all()

    completed_count = sum(1 for t, e in tasks if t.status == "Completed")
    pending_count = sum(1 for t, e in tasks if t.status == "Pending")

    admin_count = sum(1 for u in users if u.role == "admin")
    member_count = sum(1 for u in users if u.role == "member")

    return render_template(
        'admin_dashboard.html',
        users=users,
        projects=projects,
        tasks=tasks,
        completed_count=completed_count,
        pending_count=pending_count,
        admin_count=admin_count,
        member_count=member_count
    )


# ================= PROJECTS =================
@app.route('/projects', methods=['GET', 'POST'])
@login_required
def projects():

    if request.method == 'POST':

        project = Project(
            title=request.form['title'],
            description=request.form['description'],
            credential_type=request.form.get('credential_type'),
            start_date=request.form['start_date'],
            end_date=request.form['end_date'],
            user_id=current_user.id
        )

        db.session.add(project)
        db.session.commit()

        flash("Project created successfully")

    projects = Project.query.filter_by(user_id=current_user.id).all()
    return render_template("projects.html", projects=projects)


# ================= TASKS =================
@app.route('/tasks', methods=['GET', 'POST'])
@login_required
def tasks_view():

    if request.method == 'POST':

        task = Task(
            title=request.form['title'],
            status=request.form['status'],
            due_date=request.form['due_date'],
            assigned_to=request.form['assigned_to'],
            project_id=request.form['project_id'],
            user_id=current_user.id
        )

        db.session.add(task)
        db.session.commit()

        flash("Task created successfully")

    tasks = Task.query.filter_by(user_id=current_user.id).all()
    projects = Project.query.filter_by(user_id=current_user.id).all()

    return render_template("tasks.html", tasks=tasks, projects=projects)


# ================= DELETE PROJECT =================
@app.route('/project/delete/<int:project_id>')
@login_required
def delete_project(project_id):

    project = Project.query.get_or_404(project_id)

    if current_user.role != "admin" and project.user_id != current_user.id:
        flash("Access denied")
        return redirect('/projects')

    Task.query.filter_by(project_id=project.id).delete()
    db.session.delete(project)
    db.session.commit()

    flash("Project deleted")
    return redirect('/projects')


# ================= DELETE TASK =================
@app.route('/task/delete/<int:task_id>')
@login_required
def delete_task(task_id):

    task = Task.query.get_or_404(task_id)

    if current_user.role != "admin" and task.user_id != current_user.id:
        flash("Access denied")
        return redirect('/tasks')

    db.session.delete(task)
    db.session.commit()

    flash("Task deleted")
    return redirect('/tasks')


# ================= STATUS ACTIONS =================
@app.route('/task/complete/<int:task_id>')
@login_required
def complete_task(task_id):

    task = Task.query.get_or_404(task_id)

    task.status = "Completed"
    db.session.commit()

    return redirect('/tasks')


@app.route('/task/pending/<int:task_id>')
@login_required
def pending_task(task_id):

    task = Task.query.get_or_404(task_id)

    task.status = "Pending"
    db.session.commit()

    return redirect('/tasks')


# ================= LOGOUT =================
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')


# ================= RUN =================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

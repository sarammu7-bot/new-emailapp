from fastapi import APIRouter, Depends, HTTPException, Query
from asgiref.sync import sync_to_async
from typing import List, Optional
from django_backend.models import Email, Task, User, ChatMessage, TaskComment, TaskActivity, Tag, Project 
from fastapi_app.schemas.task_schemas import TaskRead, TaskCreate, TaskUpdate, CommentCreate, CommentRead, ActivityRead, TagRead, AddTagRequest, ProjectCreate, ProjectRead
from fastapi_app.routers.auth import get_current_user
from fastapi_app.routers.notifications import create_notification

router = APIRouter(prefix="/tasks", tags=["Tasks"])

def log_activity(task: Task, user: User, action: str, details: str):
    TaskActivity.objects.create(
        task=task,
        actor=user,
        action_type=action,
        details=details
    )


@router.get("/", response_model=List[TaskRead])
def list_my_tasks(
    status: Optional[str] = Query(None, description="Filter by status (todo, in_progress, done)"),
    priority: Optional[str] = Query(None, description="Filter by priority (low, medium, high)"),
    project_id: Optional[int] = Query(None, description="Filter by Project ID"),
    tag: Optional[str] = Query(None, description="Filter by Tag Name"),          
    current_user: User = Depends(get_current_user)
):
    """
    Get all tasks for the current user.
    Filters: status, priority, project_id, tag
    """
    tasks = Task.objects.filter(assigned_to=current_user) | Task.objects.filter(created_by=current_user)
    
    if status:
        tasks = tasks.filter(status=status)
    if priority:
        tasks = tasks.filter(priority__iexact=priority)
    
    if project_id:
        tasks = tasks.filter(project_id=project_id)
        
    if tag:
        tasks = tasks.filter(tags__name__iexact=tag) 
        
    return tasks.distinct() 

@router.post("/", response_model=TaskRead)
def create_task(data: TaskCreate, current_user: User = Depends(get_current_user)):
    assignee = None
    if data.assigned_to_email:
        try:
            assignee = User.objects.get(email=data.assigned_to_email)
        except User.DoesNotExist:
            raise HTTPException(status_code=404, detail="Assignee email not found")
        
        project_obj = None
    if data.project_id:
        try:
            project_obj = Project.objects.get(id=data.project_id)
        except Project.DoesNotExist:
            raise HTTPException(status_code=404, detail="Project not found")

    task = Task.objects.create(
        title=data.title,
        description=data.description,
        priority=data.priority,
        due_date=data.due_date,
        created_by=current_user,
        assigned_to=assignee,
        project=project_obj
    )

    if assignee and assignee != current_user:
        create_notification(
            recipient=assignee,
            message=f"{current_user.email} assigned you a task: {task.title}",
            type_choice="task",
            related_id=task.id
        )

    return task


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: int, data: TaskUpdate, current_user: User = Depends(get_current_user)):
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")

    if data.status and data.status != task.status:
        log_activity(task, current_user, "status_change", f"Changed status from {task.status} to {data.status}")
        task.status = data.status

    if data.priority and data.priority != task.priority:
        log_activity(task, current_user, "priority_change", f"Changed priority from {task.priority} to {data.priority}")
        task.priority = data.priority
    
    if data.assigned_to_email:
        try:
            new_assignee = User.objects.get(email=data.assigned_to_email)
            if task.assigned_to != new_assignee:
                log_activity(task, current_user, "assignment", f"Reassigned task to {new_assignee.email}")
                task.assigned_to = new_assignee
                
                create_notification(
                    recipient=new_assignee,
                    message=f"Task reassigned to you by {current_user.email}: {task.title}",
                    type_choice="task",
                    related_id=task.id
                )
        except User.DoesNotExist:
            pass 

    task.save()
    return task


@router.post("/from-email/{email_id}", response_model=TaskRead)
def create_task_from_email(email_id: int, current_user: User = Depends(get_current_user)):
    try:
        email = Email.objects.get(id=email_id)
    except Email.DoesNotExist:
        raise HTTPException(status_code=404, detail="Email not found")

    task = Task.objects.create(
        title=email.subject or f"Task from Email #{email.id}",
        description=email.body or "No content",
        created_by=current_user,
        email=email,
        priority="medium"
    )
    return task


@router.post("/from-chat/{message_id}", response_model=TaskRead)
def create_task_from_chat(message_id: int, current_user: User = Depends(get_current_user)):
    """
    Convert a Chat Message into a Task.
    """
    try:
        chat_msg = ChatMessage.objects.get(id=message_id)
    except ChatMessage.DoesNotExist:
        raise HTTPException(status_code=404, detail="Chat message not found")

    task = Task.objects.create(
        title=f"Task from Chat #{chat_msg.id}",
        description=chat_msg.content or "No content available",
        created_by=current_user,
        priority="medium"
    )
    return task

@router.post("/{task_id}/comments", response_model=CommentRead)
def add_comment(task_id: int, comment: CommentCreate, current_user: User = Depends(get_current_user)):
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")

    new_comment = TaskComment.objects.create(
        task=task,
        author=current_user,
        content=comment.content
    )
    
    if task.assigned_to and task.assigned_to != current_user:
        create_notification(
            recipient=task.assigned_to,
            message=f"{current_user.email} commented on task: {task.title}",
            type_choice="task",
            related_id=task.id
        )

    return new_comment

@router.get("/{task_id}/comments", response_model=List[CommentRead])
def list_comments(task_id: int, current_user: User = Depends(get_current_user)):
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")
        
    return task.comments.all().order_by('-created_at')


@router.get("/{task_id}/history", response_model=List[ActivityRead])
def get_task_history(task_id: int, current_user: User = Depends(get_current_user)):
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")
        
    return task.activity_log.all().order_by('-created_at')

@router.post("/{task_id}/tags", response_model=TaskRead)
def add_tag_to_task(task_id: int, tag_data: AddTagRequest, current_user: User = Depends(get_current_user)):
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        raise HTTPException(status_code=404, detail="Task not found")
    tag, created = Tag.objects.get_or_create(name=tag_data.tag_name)
    
    task.tags.add(tag)
    
    log_activity(task, current_user, "tag_added", f"Added tag: {tag.name}")
    
    return task


@router.post("/projects", response_model=ProjectRead)
def create_project(data: ProjectCreate, current_user: User = Depends(get_current_user)):
    project = Project.objects.create(
        name=data.name,
        description=data.description,
        owner=current_user
    )
    return project


@router.get("/projects", response_model=List[ProjectRead])
def list_projects(current_user: User = Depends(get_current_user)):
    return Project.objects.all()
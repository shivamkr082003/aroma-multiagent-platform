from fastapi import HTTPException

from models.project import Project


def get_owned_project(db, project_id: str, user_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project

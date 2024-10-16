from asyncio import Lock
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from kiln_ai.adapters.langchain_adapters import LangChainPromptAdapter
from kiln_ai.datamodel import Task, TaskRun
from pydantic import BaseModel

from libs.studio.kiln_studio.project_management import project_from_id

# Add this at the module level
update_run_lock = Lock()


class RunTaskRequest(BaseModel):
    model_name: str
    provider: str
    plaintext_input: str | None = None
    structured_input: Dict[str, Any] | None = None


class RunTaskOutputResponse(BaseModel):
    plaintext_output: str | None = None
    structured_output: Dict[str, Any | None] | List[Any] | None = None


class RunTaskResponse(BaseModel):
    output: RunTaskOutputResponse
    run: TaskRun | None = None


def deep_update(source, update):
    if source is None:
        return update
    for key, value in update.items():
        if isinstance(value, dict):
            source[key] = deep_update(source.get(key, {}), value)
        else:
            source[key] = value
    return source


def connect_task_management(app: FastAPI):
    @app.post("/api/projects/{project_id}/task")
    async def create_task(project_id: str, task_data: Dict[str, Any]):
        print(f"Creating task for project {project_id} with data {task_data}")
        parent_project = project_from_id(project_id)

        task = Task.validate_and_save_with_subrelations(
            task_data, parent=parent_project
        )
        if task is None:
            raise HTTPException(
                status_code=400,
                detail="Failed to create task.",
            )

        return task

    @app.get("/api/projects/{project_id}/tasks")
    async def get_tasks(project_id: str):
        parent_project = project_from_id(project_id)
        return parent_project.tasks()

    @app.get("/api/projects/{project_id}/task/{task_id}")
    async def get_task(project_id: str, task_id: str):
        parent_project = project_from_id(project_id)

        for task in parent_project.tasks():
            if task.id == task_id:
                return task

        raise HTTPException(
            status_code=404,
            detail=f"Task not found. ID: {task_id}",
        )

    @app.post("/api/projects/{project_id}/task/{task_id}/run")
    async def run_task(
        project_id: str, task_id: str, request: RunTaskRequest
    ) -> RunTaskResponse:
        parent_project = project_from_id(project_id)
        task = next(
            (task for task in parent_project.tasks() if task.id == task_id), None
        )
        if task is None:
            raise HTTPException(
                status_code=404,
                detail=f"Task not found. ID: {task_id}",
            )

        adapter = LangChainPromptAdapter(
            task, model_name=request.model_name, provider=request.provider
        )

        input = request.plaintext_input
        if task.input_schema() is not None:
            input = request.structured_input

        if input is None:
            raise HTTPException(
                status_code=400,
                detail="No input provided. Ensure your provided the proper format (plaintext or structured).",
            )

        adapter_run = await adapter.invoke_returning_run(input)
        response_output = None
        if isinstance(adapter_run.output, str):
            response_output = RunTaskOutputResponse(plaintext_output=adapter_run.output)
        else:
            response_output = RunTaskOutputResponse(
                structured_output=adapter_run.output
            )

        return RunTaskResponse(output=response_output, run=adapter_run.run)

    @app.patch("/api/projects/{project_id}/task/{task_id}/run/{run_id}")
    async def update_run_route(
        project_id: str, task_id: str, run_id: str, run_data: Dict[str, Any]
    ) -> TaskRun:
        return await update_run(project_id, task_id, run_id, run_data)


async def update_run(
    project_id: str, task_id: str, run_id: str, run_data: Dict[str, Any]
) -> TaskRun:
    # Lock to prevent overwriting concurrent updates
    async with update_run_lock:
        parent_project = project_from_id(project_id)
        task = next(
            (task for task in parent_project.tasks() if task.id == task_id), None
        )
        if task is None:
            raise HTTPException(
                status_code=404,
                detail=f"Task not found. ID: {task_id}",
            )

        run = next((run for run in task.runs() if run.id == run_id), None)
        if run is None:
            raise HTTPException(
                status_code=404,
                detail=f"Run not found. ID: {run_id}",
            )

        # Update and save
        old_run_dumped = run.model_dump()
        merged = deep_update(old_run_dumped, run_data)
        updated_run = TaskRun.model_validate(merged)
        updated_run.path = run.path
        updated_run.save_to_file()
        return updated_run

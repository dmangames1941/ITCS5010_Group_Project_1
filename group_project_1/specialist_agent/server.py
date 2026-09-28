from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from specialist_agent.rag_pipeline import RAGPipeline
from specialist_agent.task_store import create_task, get_task, update_task


app = FastAPI()
rag = RAGPipeline()


class TaskRequest(BaseModel):
    query: str


def process_task(task_id):
    task = get_task(task_id)

    try:
        update_task(task_id, status="working")
        result = rag.answer(task["query"])

        if not result["has_useful_information"]:
            update_task(
                task_id,
                status="failed",
                error="No useful information found in the knowledge base.",
            )
            return

        update_task(
            task_id,
            status="completed",
            result=result,
        )

    except Exception as e:
        update_task(
            task_id,
            status="failed",
            error=str(e),
        )


@app.post("/tasks")
def submit_task(request: TaskRequest, background_tasks: BackgroundTasks):
    task_id = create_task(request.query)
    background_tasks.add_task(process_task, task_id)

    return {
        "task_id": task_id,
        "status": "submitted",
    }


@app.get("/tasks/{task_id}")
def task_status(task_id: str):
    task = get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    return {
        "task_id": task_id,
        "status": task["status"],
        "error": task["error"],
    }


@app.get("/tasks/{task_id}/results")
def task_results(task_id: str):
    task = get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    if task["status"] != "completed":
        raise HTTPException(status_code=409, detail="Task is not completed.")

    return {
        "result": task["result"],
    }

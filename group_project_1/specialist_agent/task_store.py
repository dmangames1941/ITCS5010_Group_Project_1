import uuid

tasks = {}


def create_task(query):
    task_id = str(uuid.uuid4())

    tasks[task_id] = {
        "query": query,
        "status": "submitted",
        "result": None,
        "error": None,
    }

    return task_id


def get_task(task_id):
    return tasks.get(task_id)


def update_task(task_id, status=None, result=None, error=None):
    task = tasks.get(task_id)

    if not task:
        return None

    if status is not None:
        task["status"] = status

    if result is not None:
        task["result"] = result

    if error is not None:
        task["error"] = error

    return task

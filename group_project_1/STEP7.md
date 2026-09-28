# Step 7: timeout and failure handling

Changed files: requester_agent/a2a_client.py, requester_agent/ochestrator.py,
requirements.txt. Added tests/test_step7.py and this document.
Keep the existing spelling ochestrator.py to preserve existing imports.
Requires Python 3.11 or newer (asyncio.timeout).

## Behavior

Submission has a maximum five-second request deadline (or max_timeout when
smaller). After acknowledgment, one monotonic max_timeout deadline covers all
polling, sleeps and result retrieval. Default: 30 seconds, polling every second.
The requester stops locally at this deadline; it does not cancel the remote task.
There are no automatic submission retries, to avoid duplicate tasks.

A failed status produces A2ATaskFailedError. Network/HTTP failures produce
A2ACommunicationError. Invalid JSON, missing IDs, unknown statuses and malformed
result fields produce A2AProtocolError. Empty sources or explicitly unsupported
results produce A2ANoInformationError. All are displayed and returned by the
coordinator without invoking browser automation. A false browser verification
result is reported as an error rather than returning None.

## Specialist interface to agree with teammate

POST /tasks accepts {"query":"..."} and returns {"task_id":"unique-id"}.
GET /tasks/unique-id returns {"status":"submitted"}, {"status":"working"},
{"status":"completed"}, or {"status":"failed","error":"Explanation"}.
For no useful retrieval, return:

    {"status":"failed","error_code":"NO_RELEVANT_INFORMATION",
     "error":"No relevant knowledge-base passages were retrieved."}

GET /tasks/unique-id/results returns:

    {"result":{"category":"Password Reset","resolution":"Supported instructions",
               "sources":["source document name"],"has_useful_information":true}}

Sources must be a nonempty list of nonempty strings or source metadata objects.
Category and resolution must be nonempty strings. Alternatively a completed
result can explicitly set has_useful_information to false and will be rejected.
The specialist must decide evidence relevance; checking sources are present does
not prove they support the answer. Category must match the actual web form.

## Verification

From group_project_1:

    python -m pip install httpx playwright
    python -m unittest discover -s tests -v

Tests simulate HTTP and browser responses; no API key, running server, or browser
installation is required. They cover successful polling, explicit failure,
no evidence, unknown status, a deadline during status fetch/results fetch/sleep,
HTTP/network/JSON/acknowledgment errors, prevention of browser calls on failure,
and successful versus unsuccessful browser verification.

For a video timeout demonstration with the integrated specialist, arrange a task
that remains working, construct RequesterOchestrator(max_timeout=3,
poll_interval=0.5), and call process_user_request. Show its timeout message and
that no form submission occurs. This is a suggested integration demo, not a
claim that the unfinished specialist has been tested end to end.

## Integration limits

At the reviewed repository revision, specialist_agent implementation and main.py
are empty and the expected support_form.html is absent. Step 7 is implemented on
the requester side; the team must supply those components and test the real
success/failure workflows before submitting its full project and video.
